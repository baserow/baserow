/** Answers Kuma's model requests like OpenAI's chat completions API, from fixed scripts. */

import http from "node:http";

const PORT = Number(process.env.PORT ?? 8080);
const WORD_DELAY_MS = Number(process.env.WORD_DELAY_MS ?? 300);
const MODEL = "kuma-e2e";
// Creates the database <name> with a "Tasks" table, then answers "word1 ... word<n>".
const SCRIPT = /kuma-e2e db=(\S+) words=(\d+)/;
// Also the chat's title, which Kuma asks for without tools.
const UNSCRIPTED_ANSWER = "E2E chat";
const MODEL_CHECK_TOOL = "baserow_model_compatibility_test";
const BUILDERS_RESULT = /"(created|reused)_builders"/;
const TABLES_RESULT = /"(created|reused)_tables"/;
const USAGE = { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 };

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function textOf(message) {
  if (typeof message.content === "string") return message.content;
  return (message.content ?? []).map((part) => part.text ?? "").join("");
}

function toolCall(name, args) {
  return {
    id: `call_${name}`,
    type: "function",
    function: { name, arguments: JSON.stringify(args) },
  };
}

/** The next answer: `{ toolCall }`, `{ text }`, or `{ words }` streamed one by one. */
function nextAnswer(body) {
  const messages = body.messages ?? [];
  const tools = (body.tools ?? []).map((tool) => tool.function?.name);
  if (tools.includes(MODEL_CHECK_TOOL)) {
    return messages.at(-1)?.role === "tool"
      ? { text: "OK" }
      : { toolCall: toolCall(MODEL_CHECK_TOOL, { value: "e2e" }) };
  }
  const lastUser = messages.findLast((message) => message.role === "user");
  const prompt = lastUser ? textOf(lastUser) : "";
  const script = prompt.match(SCRIPT);
  if (tools.length === 0 || !script) {
    return { text: UNSCRIPTED_ANSWER };
  }
  const [, databaseName, wordCount] = script;
  const results = messages
    .slice(messages.lastIndexOf(lastUser))
    .filter((message) => message.role === "tool")
    .map(textOf);
  const builders = results.find((result) => BUILDERS_RESULT.test(result));
  if (!builders) {
    return {
      toolCall: toolCall("create_builders", {
        builders: [{ name: databaseName, type: "database" }],
        thought: "Create the database",
      }),
    };
  }
  if (!results.some((result) => TABLES_RESULT.test(result))) {
    return {
      toolCall: toolCall("create_tables", {
        database_id: Number(builders.match(/"id":\s*(\d+)/)[1]),
        tables: [{ name: "Tasks", primary_field_name: "Name", fields: [] }],
        add_sample_rows: false,
        thought: "Add the Tasks table",
      }),
    };
  }
  return {
    words: Array.from(
      { length: Number(wordCount) },
      (_, index) => `word${index + 1}`,
    ),
  };
}

function chunk(delta, finishReason = null) {
  return {
    id: "chatcmpl-e2e",
    object: "chat.completion.chunk",
    created: Math.floor(Date.now() / 1000),
    model: MODEL,
    choices: [{ index: 0, delta, finish_reason: finishReason }],
  };
}

async function stream(res, answer) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
  });
  const send = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);
  if (answer.toolCall) {
    send(
      chunk({
        role: "assistant",
        tool_calls: [{ index: 0, ...answer.toolCall }],
      }),
    );
    send(chunk({}, "tool_calls"));
  } else {
    const parts = answer.words ?? [answer.text];
    for (const [index, part] of parts.entries()) {
      if (res.destroyed) return;
      send(
        chunk({ role: "assistant", content: index === 0 ? part : ` ${part}` }),
      );
      if (answer.words) await sleep(WORD_DELAY_MS);
    }
    send(chunk({}, "stop"));
  }
  send({ ...chunk({}), choices: [], usage: USAGE });
  res.end("data: [DONE]\n\n");
}

function respond(res, answer) {
  const message = answer.toolCall
    ? { role: "assistant", content: null, tool_calls: [answer.toolCall] }
    : {
        role: "assistant",
        content: answer.words ? answer.words.join(" ") : answer.text,
      };
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(
    JSON.stringify({
      id: "chatcmpl-e2e",
      object: "chat.completion",
      created: Math.floor(Date.now() / 1000),
      model: MODEL,
      choices: [
        {
          index: 0,
          message,
          finish_reason: answer.toolCall ? "tool_calls" : "stop",
        },
      ],
      usage: USAGE,
    }),
  );
}

const server = http.createServer(async (req, res) => {
  // A run that stops closes its stream early; that must not crash the stub.
  res.on("error", () => {});
  if (req.method !== "POST" || !req.url.endsWith("/chat/completions")) {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: { message: `No stub for ${req.url}` } }));
    return;
  }
  let raw = "";
  for await (const piece of req) raw += piece;
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    res.writeHead(400);
    res.end();
    return;
  }
  const answer = nextAnswer(body);
  if (body.stream) {
    await stream(res, answer);
  } else {
    respond(res, answer);
  }
});

server.listen(PORT, () => {
  console.log(`kuma model stub listening on ${PORT}`);
});
