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
