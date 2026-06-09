Referral program update

New behavior:
- Users can tap 🤝 Referral Program or use /referral to get their personal invite link.
- Invite format: https://t.me/YOUR_BOT_USERNAME?start=ref_USERID
- When a referred user successfully pays for Premium via M-Pesa, the referrer automatically receives +24 hours Premium.
- Reward is only given once per referred user.
- Referral tracking is stored in premium_referrals.json.

Important:
- Free trial does not trigger referral reward.
- Admin /givepremium does not trigger referral reward.
- Only successful M-Pesa premium callback triggers the reward.
