# HAM-C

Hierarchical Auditable Memory for ChatGPT.

You type in this app. HAM-C stores facts, sends a short list to ChatGPT through the API, shows which fact was used, and deletes those facts when you delete the chat.

ChatGPT still writes the answer. It does not use ChatGPT Memory.

## Run

```text
cd HAM-C
python -m pip install -r requirements.txt
```

Optional: copy `.env.example` to `.env` and put your OpenAI key in `OPENAI_API_KEY`. Without a key, HAM-C still saves, updates, and deletes facts, and answers from the store with a local fallback.

```text
python app.py
```

Open http://127.0.0.1:5000

## Persistent accounts on Vercel (important)

Vercel cannot keep a normal SQLite file. The old `/tmp/hamc.db` setup is **wiped on every cold start**, so accounts created today disappear tomorrow (wrong password / no reset email).

Fix: use a free **Turso** database (SQLite-compatible) and set these on Vercel:

1. Create a DB at https://turso.tech  
2. Copy `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`  
3. Add both in Vercel → Project → Settings → Environment Variables  
4. Also keep your SMTP variables there so “Forgot password” emails work  
5. Redeploy

Local laptop use still works with `data/hamc.db` and does not need Turso.

## Demo the three tests

1. Middle recall  
   In one chat, send filler, then `The project codeword is ORANGE-17`, then more filler, then `What is the project codeword?`  
   HAM-C should keep `codeword = ORANGE-17` and show it under the reply.

2. Update  
   `I study at Campus North.`  
   New chat: `Which campus am I on?`  
   Then `I transferred to Campus South.`  
   Ask again. The store should show only Campus South.

3. Delete chat  
   `Remember the temporary research ID is BLUE-88.`  
   Check it in a new chat, then delete the first chat. BLUE-88 should leave the fact store and later answers.
