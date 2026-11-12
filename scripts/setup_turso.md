# Fix disappearing accounts on Vercel

## Why login fails the next day

On Vercel, HAM-C used to store SQLite in `/tmp/hamc.db`. That folder is **deleted when the server sleeps**. So accounts, passwords, chats, and reset codes vanish. Forgot-password then finds no user and sends no email.

## Fix (about 5 minutes)

1. Sign up free at https://turso.tech  
2. Create a database (e.g. `ham-c`)  
3. Copy:
   - `TURSO_DATABASE_URL` (looks like `libsql://….turso.io`)
   - `TURSO_AUTH_TOKEN`
4. In **Vercel → your HAM-C project → Settings → Environment Variables**, add both for Production (and Preview if you use it).  
5. Keep your existing **SMTP_*** variables so password-reset emails still work.  
6. Redeploy (or push to GitHub if auto-deploy is on).

After that, create a new account once — it will still be there tomorrow.
