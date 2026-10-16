# Nekked Dating

A self-hosted adult dating application with private personal symbols and explicit mutual matching. Uses Python 3.10+ and SQLite for the application; optional private translation runs separately on the same host.

## Run and test

```sh
python server.py
python -m unittest discover -s tests -v
```

Open the localhost address printed/configured by your runtime (default `127.0.0.1:8000`). Create adult accounts, save discoverable profiles, open Discover and send an interest. The other member accepts it in Likes You, or sends reciprocal interest, to create a successful match. There are no fabricated profiles or automatic acceptances.

## Automated installation

On Debian/Ubuntu, run from an updated checkout of this repository:

```sh
sudo apt-get update
sudo apt-get install -y git ansible-core
sudo ansible-playbook -i localhost, -c local ansible/install-social-platform.yml
```

The playbook installs the runtime and Nginx, pulls source without discarding local changes, exports and tests a release, stops the app for an SQLite backup, switches the release, restarts and checks endpoints. Failed application activation restores prior code/service settings where present. Database rollback is manual. A shared lock coordinates with the existing hourly updater. Existing TLS configuration is preserved. The social installer raises the managed media request limit to 8 MB. Public DNS must already point to this host for new TLS setup.

Private translation installation is enabled by default and needs a working container registry/model download connection and enough disk/memory for language models. The default language set is English, Spanish and French. Override `translation_languages` to change the installed set, or use `-e install_translation=false` to deploy the app without translation. The backend probes installed languages and shows an honest unavailable state if the local service is not ready. Translation sends only the explicitly selected matched biography or conversation message to localhost; original text remains available.

On a fresh host, add `-e enable_tls=true -e certbot_email=YOUR_EMAIL` to configure a certificate. Secure cookies require HTTPS for sign-in. The default app service is `nekkeddating`, backend port `18083`, persistent database `/var/lib/nekkeddating/nekked.sqlite3` and release link `/opt/nekkeddating-github-current`.

Create and sign in to the operator account first. Grant that existing account moderation access locally, or rerun the social playbook with `-e nekked_admin_email=YOUR_EXISTING_ACCOUNT`:

```sh
sudo python3 /opt/nekkeddating-github-current/scripts/grant-admin.py \
  --db /var/lib/nekkeddating/nekked.sqlite3 --email YOUR_EXISTING_ACCOUNT
```

Roles are stored in the database. Registering with a particular email never grants administrator privileges. No external service credentials or production accounts are fabricated.

## Personal profile and privacy

- Email/password registration, scrypt hashes, expiring HttpOnly/SameSite sessions and origin checks.
- Adult birth-date checks; optional race/ethnicity, religion and languages at sign-up, carried into the profile editor. Age is displayed from the private birth date.
- Profile identity, pronouns, sexuality, gender interests, intentions, job, education, hometown, languages, height, family/pets and lifestyle fields. Members choose which optional details appear publicly.
- Up to six photos, profile picture selection, reordering and deletion. Uploaded images are resized/re-encoded in the browser; the server bounds JPEG dimensions/size and stores binary data in SQLite.
- Up to three written public prompts with reordering, a three-choice poll, a seven-day Passing Thought, and optional voice/video prompts.
- Four private reflections: an animal and three reasons, a color and three reasons, three feelings in a solitary paradise, and three feelings in a safe but inescapable white box. These never appear publicly or affect scores.
- Your personal-symbol section shows only your zodiac, Chinese zodiac, life path and name result. Master-number descriptions appear only for master numbers actually present in your results. General number catalogs and arbitrary calculators are unavailable through the application APIs.
- Brief explanations appear first; longer meanings, calculations and methods are click-to-expand. Name-letter and birth-date arithmetic is only available to its owner.

## Discovery, explicit matching and ranking

Discover returns public teasers, photos, visible details and public prompts for eligible discoverable adult profiles. It never returns symbolic scores or detailed symbol results. Standouts selects up to five suggestions using the internal symbolic ordering, without disclosing comparisons before a match. Pause removes profiles from new discovery and preserves existing matches.

Likes can target a profile, photo or prompt and include an optional comment. Roses are stronger interests. Accepting an incoming interest or sending reciprocal interest creates one active match. Declines, Skips and Undo are stored. Free limits are eight Likes per rolling 24 hours, one Rose per rolling seven days and one Undo per rolling seven days. Incoming interests may be sorted by recency or Roses first. Common-word filtering is optional and is not comprehensive moderation.

Only active mutually accepted matches can open zodiac/name numerology/life-path/Chinese-zodiac comparisons, matched symbol pages, private conversations, translated match biographies or on-demand text-message translations. Every relevant request rechecks that connection and blocking state. Guessing a profile/connection ID does not grant access. Unmatching and blocking immediately revoke comparisons and conversation access. Discovery photos/public media are intentionally visible before a match, while private symbol calculations remain restricted.

Matched profiles can be ranked by highest overall potential, zodiac, name numerology, life path or Chinese zodiac. The preference is saved to the profile. Overall potential averages those four available symbolic methods equally. Age, race, language, religion, public prompts, polls, private reflections and relationship preferences do not affect potential scores. Gender interests constrain discovery; adult checks are mandatory. Demographic age/race/religion/language filters are intentionally absent.

The zodiac rule compares classical sun-sign elements. Chinese zodiac uses approximate Gregorian birth-year positions, not exact Lunar New Year boundaries. Life path sums all birth-date digits; name numerology uses normalized Latin A–Z values. Pythagorean reductions preserve 11, 22 and 33. Unavailable name results are omitted from the overall average. All methods expose their arithmetic or score basis on demand. These are entertainment rules, not validated personality or relationship predictions. Full natal charts, Moon/rising signs, transits and planetary synastry are not implemented.

## Messaging, expression and safety

Accepted matches have text chat with a manual Send action, suggested opener, Your Turn indicator, hidden conversations, private notes, private We Met feedback and Unmatch. Chat polls every ten seconds while an open conversation is visible. The endpoint returns the latest 200 messages; full archive pagination is not implemented. Messaging is rate-limited and remains free.

Members can upload WebM audio/video or Ogg audio (4 MB per file; ten files/20 MB total per account). Audio attachments and browser microphone recording support voice notes. Recording is initiated explicitly and limited to one minute. File format support and device permissions depend on the browser. Only authorized discovery/profile viewers or active conversation participants can retrieve referenced media; drafts remain owner-only. Account deletion removes owned media. Media validation checks size, declared type and container signature; production-grade server-side decoding/transcoding and malware screening remain necessary before an unrestricted public launch.

Friend’s Take invitations are unguessable local links expiring after seven days. Guests can submit text without an account. Submissions stay private until the profile owner approves them, and can be hidden/deleted. Invitations are not sent automatically. Guest voice/video/photo submissions are not supported. Poll responses and private meeting feedback are stored without affecting match potential.

Report and Block work from discovery, Likes and chat. Former matches can be reported from Help. Reports, support requests and submitted success stories have a real operator moderation queue. Only approved success stories are publicly displayed. The operator can resolve/dismiss cases and approve/reject stories. Member-submitted reports are allegations, not automated findings.

Settings include Pause, optional approximate activity, in-app notifications, comment filtering, preferred language and measurement units. These preferences are saved; full interface translation/unit conversion is not implemented. Export downloads the member's profile, settings, sent text messages, submitted reports and photo references as JSON; binary media must be downloaded separately. Deletion removes account/profile/session/owned content and revokes connections; reports are anonymized. Backups have separate retention controlled by the operator.

## Navigation and installation on a phone

Public pages include mission, impact, research, newsroom, careers, contact, success stories, history, safety, FAQ, trust, press, matching, identity resources, privacy, terms and accessibility. Pages avoid unsupported statistics or invented company vacancies. Navigation stays within the site. A web manifest and service worker support browser installation where available. Only the public logo is cached; account and API content is never cached by the service worker. This is an installable website, not a native Android/iOS application or an APK.

Member navigation connects Discover, Standouts, Likes You, My matches, Conversations, Profile, My symbols, Privacy, Settings, Help and role-restricted Moderation to their database-backed endpoints.

## Provider-dependent and unfinished inventory

The supplied feature list is broader than this implementation. The app does not claim complete parity with any third-party product. Working local features are described above; these remaining items are explicitly unavailable rather than simulated:

- SMS/email code verification, Google/Apple login and connected-account management.
- Selfie/face matching, verified identity/age documents and verification badges.
- Paid subscriptions, purchases, card billing, billing-portal cancellation, paid boosts, priority paid Likes and purchased credit balances.
- Native mobile apps, push/SMS/email notifications, live calling and native store purchases.
- Map search/geocoding, distance calculations and subscription-specific demographic filters.
- Automated prompt feedback, personalized generated openers, Signals badges, contact-list blocking and advanced abuse detection.
- Multi-format guest Friend’s Takes, photo-specific caption prompts and automated top-photo experiments.
- Comprehensive legal documents tailored to the operating entity/region and a staffed moderation/response service.

The GUI states when provider-dependent features are not configured. It does not show fake purchases, verified badges, phone checks or connected accounts. Authentication currently means email/password only; email ownership is not verified. Operator privacy/support details, rate limits on authentication, account recovery, robust media processing, and operational monitoring must be completed before unrestricted public launch.

Copyright 2026 Olamide Olatayo Bello. All rights reserved.
