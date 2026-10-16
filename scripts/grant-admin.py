#!/usr/bin/env python3
"""Run locally by the operator after creating and verifying their own account."""
import argparse,sqlite3
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--email',required=True);args=p.parse_args()
with sqlite3.connect(args.db) as db:
    user=db.execute('SELECT id FROM users WHERE email=?',(args.email.strip().lower(),)).fetchone()
    if not user: raise SystemExit('Create and sign in to the operator account first, then run this command again.')
    db.execute('CREATE TABLE IF NOT EXISTS account_roles(user_id INTEGER PRIMARY KEY,role TEXT)')
    db.execute("INSERT OR REPLACE INTO account_roles VALUES(?,'admin')",(user[0],))
print('Operator role granted to the existing account.')
