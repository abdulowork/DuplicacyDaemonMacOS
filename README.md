# DuplicacyDaemonMacOS

A LaunchDaemon for macOS to schedule regular backups using [Duplicacy](https://github.com/gilbertchen/duplicacy) featuring:

- **Pinging [healthchecks.io](https://healthchecks.io/) on backup completion**
- **TCC setup validation and other sanity checks**
- **Log rotation**
- **No external dependencies, except `duplicacy` binary**

## Getting Started

### Prerequisites

The daemon expects that you already have a Duplicacy repository initialized. See [init command details](https://forum.duplicacy.com/t/init-command-details/1090) if you need to initialize the repository. Initialize your repository in `/System/Volumes/Data` if you want to back up the entirety of your partition. 

The second step is to ensure that you specify storage keys using `duplicacy set -key` or have relevant Keychain entries in the `System` keychain (check using `security find-generic-password -s duplicacy /Library/Keychains/System.keychain`).

### Installing the daemon

With the repository and storage setup, clone this repository and run:
```commandline
sudo ./install.py --repository-path /path/to/repository
``` 

The script requires `sudo` to install the LaunchDaemon and set `root:wheel` ownership where appropriate. See `./install.py --help` for more options.

The script will:
1. Generate and install the launchd plist file in `/Library/LaunchDaemons/com.duplicacy_macos_daemon.backup.plist`
2. Deploy `backup_exec` binary and the `run_backup.py` script
3. Bootstrap the launchd service
4. Open the System Preferences pane and the binary deployment directory in Finder

Now grant Full Disk Access to the `com.duplicacy_macos_daemon.backup.backup_exec` binary, and you are done.

<details>
<summary>What is backup_exec and why Full Disk Access is needed</summary>

The `backup_exec` binary is needed to grant TCC permissions, such as Full Disk Access to the `duplicacy` subprocess. Without TCC permission `duplicacy` will not back up protected folders, for example the `~/Desktop`. 

For a daemon launchd determines subprocess permissions on the `Program` argument in the plist; since a python interpreter runs `run_backup.py`, it is [not possible](https://developer.apple.com/forums/thread/678819) to grant TCC permissions to the script separately. Therefore `backup_exec` acts as a proxy to grant TCC permissions to `run_backup.py` and to `duplicacy` transitively.

`backup_exec` is precompiled for convenience, but it could be recompiled using: `gcc backup_exec.c -o backup_exec`. 

If you don't want to grant Full Disk Access, disable the check using `--skip-check-for-full-disk-access`, but beware that some directories might not back up.

</details>

To start the backup process, do:
```commandline
sudo launchctl kickstart system/com.duplicacy_macos_daemon.backup
```

You will find live logs in:
```commandline
open -R /Library/Logs/com.duplicacy_macos_daemon.backup
```

## Monitoring your backups

After configuring the backup process, ensuring your backups continue running is essential. [Healthchecks.io](https://healthchecks.io/) is an outside observer perfect for the job. 

Specify your ping url using `--healthcheck https://hc-ping.com/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`, and the backup daemon will ping the url every time the backup job succeeds or something goes wrong.