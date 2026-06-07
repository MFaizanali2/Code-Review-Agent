import os
import shutil
from git import Repo, GitCommandError
from .base_tool import BaseTool

class GitHubTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="fetch_repository",
            description="GitHub repository clone karo aur files list karo"
        )

    async def execute(self, github_url: str, target_dir: str = "./temp_repo") -> dict:
        try:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)

            repo = Repo.clone_from(github_url, target_dir)
            all_files = self._get_all_files(target_dir)
            python_files = [f for f in all_files if f.endswith(".py")]
            languages = self._detect_languages(target_dir)

            return {
                "status": "success",
                "repo_path": target_dir,
                "file_count": len(all_files),
                "python_file_count": len(python_files),
                "languages": languages,
                "files": all_files,
                "python_files": python_files
            }

        except GitCommandError as e:
            return {"status": "error", "message": f"Git error: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_all_files(self, path: str) -> list:
        files = []
        for root, dirs, filenames in os.walk(path):
            dirs[:] = [d for d in dirs if d != '.git']
            for file in filenames:
                files.append(os.path.join(root, file))
        return files

    def _detect_languages(self, path: str) -> dict:
        extensions = {}
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d != '.git']
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1
        return extensions
