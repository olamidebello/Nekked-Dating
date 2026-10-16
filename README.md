# Nekked Dating

A working first version of the handwritten dating concept: reveal who you are, reflect on what matters, and discover symbolic compatibility.

## Run

Requires Python 3.12 or later, with no external packages.

```sh
python server.py
```

Open http://127.0.0.1:8000. Create an adult account, save a profile, enable discovery, and use **Discover matches**. A second account can be created in another browser session to exercise matching. There are no fake members. Profile visibility is off by default.

```sh
python -m unittest discover -s tests -v
```

## Implemented

- Registration, sign-in, sign-out, scrypt password hashes, expiring HttpOnly sessions.
- Server-side age and profile validation; adults only.
- Private birth date, birth time and location, surname and reflection answers.
- Animal, color, paradise and white-box prompts, each with three words/feelings.
- Opt-in discovery; first name, bio and symbolic overview only.
- Approximate Western sun sign, Gregorian birth-year Chinese zodiac, life-path and Pythagorean name numerology.
- Explainable matching: equal weights for sun-sign elements, birth-year zodiac, life-path, and stated preferences in emotional connection, intimacy, finances, living together and moods.
- Responsive interface, accessible labels, account deletion, and persistent SQLite storage.

## Meaning and limits

Astrology/numerology scores are entertainment and reflection, not validated predictions. Questionnaire interpretations are self-reflection prompts and do not infer psychological traits or determine rankings. Preference percentages are deterministic rule outputs, not probabilities.

This version **does not calculate a full natal chart**. Time and location are stored for future chart support. Chinese zodiac is explicitly labeled an approximate Gregorian birth-year calculation; Lunar New Year handling is not implemented. Western sun-sign boundaries are approximate, particularly at cusp dates.

## Deployment boundary

This is an initial working application, not a public-launch-ready dating service. Before public launch add verified adult onboarding, login/registration rate limits, email verification and account recovery, reporting/blocking/moderation, operational monitoring, backup/deletion policy, and operator-specific privacy/terms/contact details. Messaging and payments are not implemented.

Use a TLS reverse proxy and set `NEKKED_SECURE_COOKIE=1` and `NEKKED_ORIGIN=https://your-domain`. Default binding is localhost. Set `NEKKED_HOST`, `PORT`, and `NEKKED_DB` if needed. Restrict database access; it contains sensitive plaintext profile fields. Do not commit the database or secrets. Data deletion removes account and sessions from the live database, but operators must separately manage backups.

## Ownership

Copyright 2026 Olamide Olatayo Bello. All rights reserved. No open-source license has been selected.

## Branding

The supplied gold-and-purple zodiac/dragon logo is included unchanged as `static/logo.png`. Slogan: “.. stripe down to your true self to find your true match”.

## Compatible-profile registration

After creating an account (with password confirmation), members complete six grouped sections: identity; private celestial birth details; gender, preferred genders, mutual age range, relationship goal, current city/region, optional interests and family/smoking preferences; optional private full birth name for numerology; relationship preferences; and private reflections. Discovery remains opt-in. The supplied dragon/heart/zodiac logo appears throughout onboarding.

Mutual age and gender choices filter discovery. Relationship goals and disclosed family/smoking preferences contribute to the stated-preference component of the score. Interests and current location are saved privately for future matching support; they do not currently affect ranking. Full birth name is optional and overrides first/last name for Pythagorean numerology. Non-Latin-only names return an unavailable name number. Existing profiles remain compatible with the expanded schema.

Symbolic calculations retain the approximation limits documented above. The Chinese dragon is branding; a member's birth-year animal is calculated from their own date rather than assigned Dragon to everyone. This update is source code only and does not deploy the service.

## Celestial interface

The interface uses a midnight-purple, rose and gold theme, the supplied dragon/heart logo, responsive orbital hero artwork and three concept cards. Public links navigate to the concept, matching journey and account form. Signed-in navigation opens My story, Discover, My symbols and Privacy with explicit active states. Account creation and sign-in have separate form modes. Saving a profile opens a four-card symbolic overview. Privacy links to the discovery control and account deletion. No sample members or unsupported messaging/payment buttons are shown.

## Reflection, photos and compatibility update

The four prompts ask for an animal and three reasons, a representative color and three reasons, three feelings in a solitary paradise, and three feelings in an inescapable white box where the member is safe and not hungry. Scene descriptions are optional; reasons/feelings support up to 500 characters each. Reflections remain private and do not affect scores.

Members can upload up to six photos, choose the first as their profile picture, reorder the primary photo, and remove photos. The browser resizes to 1200 pixels and re-encodes JPEG to remove original metadata. The server limits uploads to 500 KB and dimensions to 1600 pixels, checks JPEG markers, stores binary images in SQLite, and serves them through authenticated authorization checks. Original image files are not retained. Photos become visible after saving the profile, only to members with mutually eligible age/gender preferences and discovery enabled on both profiles. Uploaded drafts remain available in the editor. Account deletion also removes photos from the live database. Before public launch add robust server-side image decoding/re-encoding, moderation and the other deployment safeguards above.

Expandable symbol cards show traditional meanings for the member and each eligible match: approximate Western sun sign, Gregorian birth-year Chinese animal, life path and name number. Only the owner receives birth-date digit and name-letter arithmetic. Life path sums every date digit; both calculations preserve master numbers 11, 22 and 33 during reduction. These conventions vary by numerology tradition. Match responses never contain the birth date, full name, private reflections or calculation inputs.

Each eligible match shows Love (mean emotional/intimacy alignment), Living (living alignment), Money (financial alignment), and Communication (a separate communication preference, falling back to the stored moods preference for older profiles). Equal preferences score 90 and different preferences 50. Expand each domain for its basis. These are rule-based preference alignment scores, not validated predictions. Existing overall symbolic scoring remains visible.

## Dedicated symbol pages

Every symbol tile is a full-card link to `/symbols/me/{kind}` or `/symbols/{match_id}/{kind}`. Supported kinds are sun_sign, chinese_zodiac, life_path and name_number. Pages explain the symbol's traditional personality themes, strengths, growth areas, relationship prompts, calculation method and exact role in matching. Symbols are presented as traditions for reflection, not causes or scientific determinations of personality.

Details load from authenticated `/api/symbols/...` endpoints. Matched-profile requests recheck mutual discovery, age and gender eligibility on every visit, including direct links and refreshes. Only the owner receives the private calculation; matched members see public symbols and interpretations. Pages support direct navigation, refresh, browser Back, links to the other symbols and a return to My symbols or Discover.
