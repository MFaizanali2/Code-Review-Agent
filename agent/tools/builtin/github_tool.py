import os
import shutil
from git import Repo, GitCommandError
from agent.tools.base import BaseTool, ToolResult, ToolSchema


class GitHubTool(BaseTool):
    @property
    def name(self) -> str:
        return "fetch_repository"

    @property
    def description(self) -> str:
        return "Clone a GitHub repository and list its files"

    async def run(self, tool_input: dict) -> ToolResult:
        github_url = tool_input.get("github_url", "")
        target_dir = tool_input.get("target_dir", "./temp_repo")
        try:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)

            repo = Repo.clone_from(github_url, target_dir)
            all_files = self._get_all_files(target_dir)
            python_files = [f for f in all_files if f.endswith(".py")]
            languages = self._detect_languages(target_dir)

            return ToolResult(
                success=True,
                data={
                    "status": "success",
                    "repo_path": target_dir,
                    "file_count": len(all_files),
                    "python_file_count": len(python_files),
                    "languages": languages,
                    "files": all_files,
                    "python_files": python_files,
                },
            )

        except GitCommandError as e:
            return ToolResult(success=False, data={}, error=f"Git error: {str(e)}")
        except Exception as e:
            return ToolResult(success=False, data={}, error=str(e))

    def _get_all_files(self, path: str) -> list:
        files = []
        for root, dirs, filenames in os.walk(path):
            dirs[:] = [d for d in dirs if d != ".git"]
            for file in filenames:
                files.append(os.path.join(root, file))
        return files

    def _detect_languages(self, path: str) -> dict:
        extensions = {}
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d != ".git"]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1
        return extensions

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "github_url": {
                    "type": "string",
                    "description": "Full GitHub repository URL (https://github.com/owner/repo)",
                },
                "target_dir": {
                    "type": "string",
                    "description": "Local directory to clone into (optional)",
                },
            },
            required=["github_url"],
        )
