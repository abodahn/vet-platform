#!/usr/bin/env bash
# Give the server SSM Session Manager access, so shell access stops depending on
# a security-group rule that names your home IP address.
#
# WHY THIS EXISTS
#
# Port 22 is open to a handful of /32 rules, one per machine that has ever needed
# in. Egyptian consumer broadband reassigns addresses constantly — during two days
# of work this IP changed FIVE times, and every change meant: notice SSH hangs,
# re-authenticate to AWS, edit the rule, retry. Each stale rule left behind is a
# permanent doorway from an address the ISP has since given to a stranger.
#
# Session Manager removes the problem rather than managing it. The agent on the
# instance opens an OUTBOUND connection to the SSM service; you connect through
# the AWS API and are authenticated by IAM. No inbound port, no address to
# allow-list, nothing to update when the address changes. Sessions are logged in
# CloudTrail, which an SSH key in a file is not.
#
# ORDER MATTERS. This script does NOT close port 22. Prove a session works first,
# then revoke the rules by hand — closing the door before testing the new one is
# how you end up with a server nobody can reach.
#
#   bash deploy/enable_ssm.sh              # set it up
#   aws ssm start-session --target <id>    # then test, THEN close port 22
#
# Not CloudFormation or CDK, deliberately: this instance was built by hand and
# has no stack. Importing a live server into a new stack to attach one role is a
# bigger risk than the role is worth. The steps live here so they are repeatable
# and reviewable, which is what the IaC preference is actually for. If a stack is
# ever introduced, this belongs in it.
set -euo pipefail

INSTANCE_ID="${ALEEFY_INSTANCE_ID:-i-0bda341563744e468}"
REGION="${AWS_REGION:-eu-central-1}"
ROLE_NAME="${ALEEFY_SSM_ROLE:-AleefySSMRole}"
PROFILE_NAME="$ROLE_NAME"

echo "instance : $INSTANCE_ID"
echo "region   : $REGION"
echo "role     : $ROLE_NAME"
echo

# ── 1. The role the INSTANCE assumes ─────────────────────────────────────────
# Trust policy names ec2.amazonaws.com: only an EC2 instance may assume it, and
# only via an instance profile. It grants nothing on its own.
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "role already exists — leaving it alone"
else
  aws iam create-role --role-name "$ROLE_NAME" \
    --description "Lets the Aleefy server be managed by SSM Session Manager" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ec2.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }' >/dev/null
  echo "role created"
fi

# AmazonSSMManagedInstanceCore is the AWS-managed policy for exactly this, and
# nothing more. Do not widen it: a role on a clinic's server is a standing grant,
# and Session Manager needs no S3, no EC2 and no database access to work.
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
echo "policy attached: AmazonSSMManagedInstanceCore"

# ── 2. The instance profile that carries it ──────────────────────────────────
if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
  echo "instance profile already exists"
else
  aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
  echo "instance profile created"
  # IAM is eventually consistent; associating a profile the API has not finished
  # creating fails with a confusing "not found".
  sleep 10
fi

if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" \
     --query 'InstanceProfile.Roles[0].RoleName' --output text 2>/dev/null | grep -q "$ROLE_NAME"; then
  echo "role already in the profile"
else
  aws iam add-role-to-instance-profile \
    --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME"
  echo "role added to the profile"
  sleep 10
fi

# ── 3. Attach it to the running instance ─────────────────────────────────────
# No restart, no downtime: the instance picks the credentials up from the
# metadata service, and the agent retries until they appear.
EXISTING=$(aws ec2 describe-iam-instance-profile-associations --region "$REGION" \
  --filters "Name=instance-id,Values=$INSTANCE_ID" \
  --query 'IamInstanceProfileAssociations[?State==`associated`].AssociationId' \
  --output text 2>/dev/null || true)

if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  echo "an instance profile is already associated ($EXISTING) — leaving it"
else
  aws ec2 associate-iam-instance-profile --region "$REGION" \
    --instance-id "$INSTANCE_ID" \
    --iam-instance-profile "Name=$PROFILE_NAME" >/dev/null
  echo "instance profile associated"
fi

echo
echo "waiting for the agent to register (it polls, so this is not instant)…"
for i in $(seq 1 30); do
  STATUS=$(aws ssm describe-instance-information --region "$REGION" \
    --query "InstanceInformationList[?InstanceId=='$INSTANCE_ID'].PingStatus" \
    --output text 2>/dev/null || true)
  if [ "$STATUS" = "Online" ]; then
    echo "registered: Online after ~$((i*10))s"
    break
  fi
  sleep 10
done

if [ "${STATUS:-}" != "Online" ]; then
  echo
  echo "NOT registered yet. This is usually just slow — the agent polls every few"
  echo "minutes. Re-check with:"
  echo "  aws ssm describe-instance-information --region $REGION"
  echo "Do NOT close port 22 until it reads Online and a session opens."
  exit 1
fi

cat <<'NEXT'

Now TEST it, before changing anything else:

  aws ssm start-session --target i-0bda341563744e468 --region eu-central-1

Only once that gives you a shell, close the door behind you — list the SSH
rules, then revoke each one:

  aws ec2 describe-security-group-rules \
    --filters Name=group-id,Values=sg-0a5b3df2c045bab3b \
    --query "SecurityGroupRules[?FromPort==\`22\`].[SecurityGroupRuleId,CidrIpv4,Description]" \
    --output table

  aws ec2 revoke-security-group-ingress \
    --group-id sg-0a5b3df2c045bab3b --security-group-rule-ids <id> …

Keep the SSH key. Session Manager depends on the agent, the IAM role and the
AWS API all working; a key and a temporarily-reopened rule is the way back in on
the day one of those does not.
NEXT
