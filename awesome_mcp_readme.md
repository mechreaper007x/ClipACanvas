# Registry Submission Workbook — Clip.A.Canvas

Since registry submissions require logging in with your GitHub account or using browser interfaces, you can complete the submissions in seconds using the following step-by-step instructions and prepared files.

---

## 🐱 1. Smithery.ai Submission
The `clipacanvas` package is already indexed on Smithery under the namespace `creatorsavya/clipacanvas`!
*   **Web Listing**: `https://smithery.ai/servers/creatorsavya/clipacanvas`
*   **Action Required**:
    1. Go to `https://smithery.ai` and sign in with your GitHub account (`mechreaper007x`).
    2. Smithery will automatically link repositories under your account. Ensure the listing points to the correct PyPI package `clipacanvas-mcp`.
    3. The workspace already contains a validated [smithery.yaml](file:///C:/Users/Savyasachi%20Mishra/Desktop/clipacanvas/smithery.yaml) file, which contains the correct PyPI mappings.

---

## 🦎 2. Glama.ai Submission & Verification
Glama.ai allows you to claim ownership of your listed servers by hosting a verification JSON file.
*   **Prepared File**: We created [.well-known/glama.json](file:///C:/Users/Savyasachi%20Mishra/Desktop/clipacanvas/.well-known/glama.json) in your project. It contains:
    ```json
    {
      "maintainerEmail": "creatorsavya@gmail.com"
    }
    ```
*   **Steps to Submit**:
    1. Deploy the current codebase containing the `.well-known/` folder to Vercel (or push it to GitHub if Vercel redeploys automatically).
    2. Go to **[glama.ai/mcp/servers](https://glama.ai/mcp/servers)**.
    3. Click **"Add server"** and enter the repository URL: `https://github.com/mechreaper007x/ClipACanvas`.
    4. Sign in to Glama.ai using the email `creatorsavya@gmail.com` to automatically match and claim ownership of the listing.

---

## 🛠️ 3. dotmcp.io Submission
dotMCP provides zero-config tunneling and visual tools for running MCP servers globally.
*   **Steps to submit / connect**:
    1. Go to **[dotmcp.io](https://dotmcp.io)** and log in with your GitHub account.
    2. Click **"Publish Server"** or **"Add Connector"** on the dashboard.
    3. Enter the public PyPI name `clipacanvas-mcp` or the repository link: `https://github.com/mechreaper007x/ClipACanvas`.
    4. You can also run it via the dotMCP tunnel CLI on your local system if you want to expose it for remote agents:
       ```bash
       npx dotmcp-tunnel --command "uvx clipacanvas-mcp"
       ```

---

## 🌐 4. Official Model Context Protocol Registry
We created the required registry manifest at [.mcp/server.json](file:///C:/Users/Savyasachi%20Mishra/Desktop/clipacanvas/.mcp/server.json).

*   **Steps to Publish**:
    1. Authenticate with GitHub through the publisher CLI:
       ```bash
       npx @modelcontextprotocol/mcp-publisher login github
       ```
    2. Publish your manifest to the official registry:
       ```bash
       npx @modelcontextprotocol/mcp-publisher publish
       ```
    3. Once published, your server will be discoverable directly in the official MCP directory under the namespace `io.github.mechreaper007x/clipacanvas`.
