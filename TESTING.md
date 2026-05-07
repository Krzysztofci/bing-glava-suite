# Testing

## Live environment testing (XFCE)

Testing on a live Linux Mint XFCE image is the most reliable way to verify
a clean installation from scratch. The procedure below documents exactly how
the v0.5.0 test was performed.

### Requirements

- Linux Mint XFCE ISO on a USB drive
- Machine with at least 8 GB RAM (required for `toram`)
- Internet connection

### 1. Boot with `toram`

Loading the entire live system into RAM avoids I/O bottlenecks from the USB
drive, which would otherwise cause the installer to stall or behave unexpectedly.

At the GRUB menu, press **`e`** to edit the boot entry.
Find the line containing `quiet splash` and append `toram` after it:

```
quiet splash toram
```

Press **F10** to boot. The system will take longer to start than usual
(copying to RAM), but will be significantly faster once running.
### 2. Before install

Before running the installer on a live CD/USB environment, remove the CD-ROM
repository from apt sources, otherwise the installation will fail:

    sudo sed -i '/cdrom/d' /etc/apt/sources.list

This is required because live systems include a cdrom: entry in sources.list
that causes apt to fail when the disc is not accessible.

### 3. Install the suite

```bash
sudo apt install git
git clone -b feature/modular-gui https://github.com/Krzysztofci/bing-glava-suite.git
cd bing-glava-suite
sudo ./install.sh
```

Follow the installer prompts. GLava will be downloaded automatically
from GitHub Releases if not present.

### 4. Memory management

On an 8 GB machine, RAM is shared between the live system, the suite, and
any audio player. After installation:

```bash
sudo apt clean
```

If memory is critically low, drop caches:

```bash
sudo sync
echo 3 | sudo tee /proc/sys/vm/drop_caches
```

**Do not open a browser** — it will consume too much RAM and make the test
unreliable.

### 5. Test audio playback

GLava needs an audio source to visualize. `mpv` works well in a live
environment and is lightweight. Install it:

```bash
sudo apt install mpv
```

Use the included radio script to start a stream:

```bash
bash tools/radio.sh
```

This plays internet radio through `mpv` without a GUI — enough to drive all
GLava shader modules for visual testing.

### 6. What to verify

- [ ] Installer completes without errors
- [ ] GLava starts automatically after install (or after `systemctl --user start glava-color-daemon`)
- [ ] GUI launches: `glava-gui`
- [ ] All 5 shader modules switch correctly (bars, circle, wave, radial, graph)
- [ ] Colors update when fetching a Bing wallpaper
- [ ] Shader profiles save and load
- [ ] Geometry auto-detect returns sensible values

---

## Tested configurations

| Desktop | Environment | Result |
|---|---|---|
| Linux Mint 22.x XFCE | Live (toram) + normal install | ✅ Fully tested |
| Linux Mint Cinnamon | Normal install | ✅ Works |
| Linux Mint Cinnamon | Live (toram) | ⏳ Not yet tested |
