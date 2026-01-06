Docker
------

Build the image (from the project root):

```powershell
docker build -t shell-server:latest .
```

Run the container:

```powershell
docker run --rm -it shell-server:latest
```

This container uses the `uv` package manager as you do locally and runs the app with:

```
uv run shell_server.py
```

If your project needs packages declared in `pyproject.toml`/`uv.lock`, consider running `uv install` in the Dockerfile to pre-install dependencies.

To interact with the shell server docker container you can use the client tool like Claude Desktop and
configure the claude_desktop_config.json file to run the server when the claude desktop launches.

you edit the claude_desktop_config.json as follows:

```
{
  "mcpServers": {
    "ShellServer": {
        "command": "podman",
        "args": [
            "run",
            "-i",
            "--rm",
            "--init",
            "-e",
            "DOCKER_CONTAINER=true",
            "shell_server:latest"
        ]
    },
  }
}
```
You can test the mcp by going to claude desktop chatbox and asking it to list files in your home directory,
as the server is running inside the docker container it will list all files inside the containers home directory.