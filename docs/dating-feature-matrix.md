# Dating feature implementation matrix

This is a Nekked Dating implementation inventory, not a claim of exact Hinge parity. The existing backend, schema, UI and tests supply the implemented rows. External-provider and native-app gaps are intentionally listed. Availability on a deployed host still requires deployment and operational validation.

Reference: https://hinge.co/how-we-connect-daters and https://help.hinge.co/hc/en-us/articles/36311177115027-Roses . Hinge's complete internal implementation and operator console are not public. No Hinge code, branding, media or private APIs are used.

| # | Feature | GUI / backend | Scope or remaining work |
|---|---|---|---|
| 1 | Adult signup | Registration / users, onboarding | Birth-date declaration; no identity verification |
| 2 | Login and sessions | Login / hashed sessions | Email/password; ownership unverified |
| 3 | Change password | Settings / account/password | Current password required, bounded attempts, all sessions revoked |
| 4 | Password recovery | Unavailable | Requires verified delivery and secure recovery workflow |
| 5 | Profile editor | My personal profile / profile | Visibility controls and structured fields |
| 6 | Photos | Profile / photos | First picture before match; private gallery after match |
| 7 | Written prompts | Profile / profile | Up to three, reorderable |
| 8 | Prompt poll | Profile, Discover / poll/vote | Three choices |
| 9 | Voice/video prompts | Profile / media | Bounded browser uploads; decoding hardening outstanding |
| 10 | Passing Thought | Profile / thoughts | Seven-day lifetime |
| 11 | Friend's Take | Profile / take invitations | Owner-approved guest text; no guest media |
| 12 | Discover | Discover / discover | Adult eligibility, mutual preferences, pause and blocking |
| 13 | Skip and Undo | Discover / social endpoints | Stored skips, quota-controlled undo |
| 14 | Likes and comments | Discover / likes | Profile/photo/prompt targets; rolling free limits |
| 15 | Roses | Discover / likes | Weekly free allowance and prepaid packs |
| 16 | Standouts | Standouts / standouts | Own symbolic ordering, not Hinge's algorithm |
| 17 | Likes You | Likes You / likes | Incoming likes, acceptance and decline |
| 18 | Mutual matching | Likes / connections | Explicit consent, serialized quota checks |
| 19 | Compatibility | My matches / compatibility | Entertainment rules, private until mutual match |
| 20 | Chat | Conversations / messages | Text and voice; polling, latest 200 messages |
| 21 | Your Turn | Conversations / conversations | Last sender based indicator |
| 22 | Hidden chats and notes | Conversations / connection settings | Private per member |
| 23 | We Met | Conversations / feedback | Private notes, no learning model |
| 24 | Translation | Matched profiles and chat / translation | Local translation service required |
| 25 | Unmatch | Conversations / unmatch | Revokes access |
| 26 | Report and block | Discovery, Likes, Help, chat / reports, blocks | Human moderation queue |
| 27 | Pause and activity | Settings / account settings | Approximate activity sharing optional |
| 28 | Notifications | Settings / notices | In-app only |
| 29 | Data export and deletion | Settings, Privacy / export, delete | Backup retention is separate |
| 30 | Membership marketplace | Memberships / commerce | Prepaid fixed terms; no auto renewal |
| 31 | Payment gateways | Memberships, Admin / gateways | Stripe, PayPal, Paystack, Flutterwave need credentials |
| 32 | Operator controls | Admin / super endpoints | Roles, suspensions, plans, gateway settings, audit |
| 33 | Dating rooms | Dating / dating_room tables | Explicit opt-in, reports and removal |
| 34 | Meetup proposals | Dating / meetup tables | Match and invitee consent; no bookings/maps |
| 35 | Mobile browser install | Download / manifest, service worker | PWA; no native APK or iOS build |
| 36 | Native push and store purchases | Unavailable | Native projects, credentials, platform integrations required |
| 37 | Google/Apple/phone authentication | Unavailable | Providers and account-linking workflow required |
| 38 | Selfie/face verification | Unavailable | Verification provider, consent, retention and review required |
| 39 | Geographic radius matching | Unavailable | No geocoder or distance calculations |
| 40 | Paid boosts and priority likes | Unavailable | No paid visibility product implemented |
| 41 | Personalized recommendation model | Unavailable | Existing symbolic ranking is separate |
| 42 | Generated prompt feedback/openers | Unavailable | Only a static opener suggestion exists |
| 43 | Contact-list blocking | Unavailable | No address-book import implemented |
| 44 | Public corporate pages | Community / static pages | Mission, safety, privacy, support and reviewed stories |

## Deploy

Run on the existing Debian/Ubuntu hosting server from an updated repository checkout:

```sh
git pull --ff-only
sudo ansible-playbook -i localhost, -c local ansible/install-dating-features.yml
```

Existing release automation runs the Python test suite, backs up SQLite and the commerce encryption key, deploys a release and checks health. Code rollback exists; database rollback is manual. Authentication checks in the wrapper are smoke checks, not proof of full feature parity. Use `-e install_translation=false` if translation model downloads are unavailable. It reuses the existing installer’s super-admin account selection; set `-e nekked_super_admin_email=YOUR_EXISTING_OPERATOR_EMAIL` explicitly on other installations.
