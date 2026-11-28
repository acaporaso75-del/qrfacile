// Local-only PostgreSQL WASM integration check. Supply the installed PGlite module path.
// No production connection, credentials, or persistent database are used.
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const { PGlite } = await import(pathToFileURL(process.argv[2]).href);
const db = new PGlite();
let checks = 0;
const same = (actual, expected) => { assert.equal(actual, expected); checks++; };
await db.exec(`
CREATE TABLE orders(id bigserial PRIMARY KEY);
CREATE TABLE credit_ledger(
 id bigserial PRIMARY KEY,user_id bigint NOT NULL,credit_type text NOT NULL,
 delta integer NOT NULL,reason text,ref_table text,ref_id bigint,created_at bigint NOT NULL
);
CREATE VIEW available_credit_ledger AS SELECT * FROM credit_ledger;
CREATE VIEW credit_balance AS SELECT user_id,credit_type,COALESCE(SUM(delta),0) AS balance
 FROM available_credit_ledger GROUP BY user_id,credit_type;
CREATE TABLE existing_labels(id integer PRIMARY KEY, expires_at bigint);
INSERT INTO existing_labels VALUES(1,9999999999);
`);
const migration = await readFile(new URL('../sql/2026_annual_wine_packages.sql', import.meta.url), 'utf8');
await db.exec(migration);
await db.exec(migration); // idempotent
checks++;
const now = Math.floor(Date.now()/1000);
const balance = async (uid=1) => Number((await db.query(
 "SELECT COALESCE(SUM(delta),0) AS n FROM available_credit_ledger WHERE user_id=$1 AND credit_type='wine'", [uid])).rows[0].n);
const insert = async (delta, {uid=1, expiry=null, order=null, reason='test'}={}) => db.query(
 "INSERT INTO credit_ledger(user_id,credit_type,delta,reason,ref_table,ref_id,created_at,expires_at) VALUES($1,'wine',$2,$3,'orders',$4,$5,$6) RETURNING id",
 [uid,delta,reason,order,now-100,expiry]);
await insert(3);
same(await balance(),3);
await insert(15,{expiry:now+1000,order:1,reason:'annual_purchase'});
await insert(50,{expiry:now+2000,order:2,reason:'annual_purchase'});
await insert(-2);
same(await balance(),66);
same(Number((await db.query("SELECT annual_used FROM credit_ledger WHERE ref_id=1")).rows[0].annual_used),2);
same(Number((await db.query("SELECT annual_used FROM credit_ledger WHERE ref_id=2")).rows[0].annual_used),0);
await assert.rejects(insert(15,{expiry:now+1000,order:1,reason:'annual_purchase'}), /duplicate key/);
checks++;
await db.exec("UPDATE credit_ledger SET expires_at=1 WHERE ref_id=1");
same(await balance(),53); // 13 unused annual units expire; legacy 3 preserved.
await insert(-51); // 50 from second grant, 1 perpetual
same(await balance(),2);
await db.exec("UPDATE credit_ledger SET expires_at=1 WHERE ref_id=2");
same(await balance(),2); // fully used grant: no second deduction
await assert.rejects(insert(-3), /Insufficient/);
checks++;
same(await balance(),2);
await db.exec('BEGIN');
await insert(15,{expiry:now+1000,order:3,reason:'annual_purchase'});
await insert(-2);
await db.exec('ROLLBACK');
same(await balance(),2);
same(Number((await db.query("SELECT COUNT(*) AS n FROM credit_ledger WHERE ref_id=3")).rows[0].n),0);
await insert(15,{uid:2,expiry:now-1,order:4,reason:'annual_purchase'});
same(await balance(2),0);
await assert.rejects(insert(-1,{uid:2}), /Insufficient/);
checks++;
same(Number((await db.query('SELECT expires_at FROM existing_labels WHERE id=1')).rows[0].expires_at),9999999999);
await assert.rejects(insert(-1,{expiry:now+100}), /Invalid annual grant/);
checks++;
same(Number((await db.query("SELECT balance FROM credit_balance WHERE user_id=1 AND credit_type='wine'")).rows[0].balance),2);
await db.close();
console.log('PASS: '+checks+' annual package PostgreSQL checks (PGlite, in-memory).');
