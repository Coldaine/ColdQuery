
import { InputPrompt } from "fastmcp";

export const analyzeQueryPrompt = {
    name: "analyze-query",
    description: "Ask the assistant to analyze a SQL query for performance and correctness.",
    arguments: [
        {
            name: "query",
            description: "The SQL query to analyze",
            required: true
        }
    ],
    load: async (args: { query: string }) => {
        return {
            messages: [
                {
                    role: "user",
                    content: {
                        type: "text",
                        text: `Please analyze the following SQL query for performance issues, potential bugs, and adherence to best practices.

Query:
\`\`\`sql
${args.query}
\`\`\`

If possible, use the \`pg_query\` tool with the \`explain\` action to get the query execution plan.`
                    }
                }
            ]
        };
    }
};
