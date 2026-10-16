#!/usr/bin/env python3
"""Operator-only elevation of an existing account. Never creates passwords or auto-promotes signups."""
import argparse,sqlite3,time
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--email',required=True);p.add_argument('--role',choices=['admin','super_admin'],default='admin');p.add_argument('--defer',action='store_true');args=p.parse_args()
with sqlite3.connect(args.db) as db:
    db.execute('CREATE TABLE IF NOT EXISTS account_roles(user_id INTEGER PRIMARY KEY,role TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS access_intents(email TEXT PRIMARY KEY,role TEXT,status TEXT,created REAL)')
    email=args.email.strip().lower();user=db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
    if not user:
        if not args.defer:raise SystemExit('Account not found. Create and sign in to this account first, then rerun elevation.')
        db.execute('INSERT OR REPLACE INTO access_intents VALUES(?,?,?,?)',(email,args.role,'pending_existing_account',time.time()))
        print('PENDING: account does not exist. No privileges granted. Create the account, then rerun this installer.');
    else:
        db.execute('INSERT OR REPLACE INTO account_roles VALUES(?,?)',(user[0],args.role))
        db.execute('INSERT OR REPLACE INTO access_intents VALUES(?,?,?,?)',(email,args.role,'applied',time.time()))
        print('APPLIED: existing account promoted to '+args.role+'. Sign out and sign in again.')
