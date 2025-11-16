# Repository Remotes

This local checkout does not have any Git remotes configured. You can verify this with:

```bash
git remote -v
```

If you expect a remote such as `origin`, you will need to add it manually. Replace the placeholder URL with either the SSH or HTTPS URL of your GitHub repository:

```bash
# SSH example
git remote add origin git@github.com:joedobrow/hero_stats.git

# HTTPS example
git remote add origin https://github.com/joedobrow/hero_stats.git
```

If you're using SSH you will need a configured key that has access to the repository. For HTTPS you can authenticate with a personal access token when prompted.

After adding the remote, double-check that the remote is configured as expected:

```bash
git remote -v
```

With the remote in place, push the existing history and set the upstream for the current branch (replace `work` with whatever branch you intend to push):

```bash
git push -u origin work
```

Once the upstream is set, future pushes can be done with a simple:

```bash
git push
```
