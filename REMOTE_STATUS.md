# Repository Remotes

This local checkout does not have any Git remotes configured. You can verify this with:

```bash
git remote -v
```

If you expect a remote such as `origin`, you will need to add it manually:

```bash
git remote add origin git@github.com:joedobrow/hero_stats.git
```

After adding the remote, you can push the existing history:

```bash
git push -u origin work
```
