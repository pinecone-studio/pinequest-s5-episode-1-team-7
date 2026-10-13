# Hardware test plan: desktop app (TDD 8.2)

Goal: show that the **Pathology Triage** desktop app installs and runs fully offline on the clinic PCs the
TDD targets (5.1: Intel Core i3 8th gen / Ryzen 3, 8 GB RAM, no dedicated GPU) on **Windows 10/11, Ubuntu
22.04 LTS and macOS**, and that it meets the speed targets (5.2: under 1.5 s AI inference per slide on CPU;
8.2: heatmap ready within 3 s).

One tester per machine. It takes about 30 minutes. Fill in one [results sheet](#results-sheet) per machine and
attach it to a GitHub issue titled `Hardware test: <OS> <CPU>`.

## Machines to cover

| # | OS | CPU class | RAM | GPU | Why |
|---|---|---|---|---|---|
| 1 | Windows 11 | quad-core (i3-8100 / Ryzen 3 or similar) | 8 GB | integrated only | TDD minimum spec |
| 2 | Windows 10 | dual-core (any) | 8 GB | integrated only | Low-end clinic PC |
| 3 | Ubuntu 22.04 LTS | quad-core | 8 GB | integrated only | Linux clinics |
| 4 | Ubuntu 22.04 LTS | dual-core | 4–8 GB | none | Worst case |
| 5 | macOS (Apple silicon) | any | 8 GB | integrated | Development and demo machine |

## You need

- The installer for the machine:
  - Windows: `Pathology Triage Setup <version>.exe`
  - Linux: `Pathology Triage-<version>.AppImage`
  - macOS: `Pathology Triage-<version>-arm64.dmg`

  They come from the **Desktop build** GitHub Actions run (Artifacts), or from building on that OS with
  `frontend/README.md` → "Desktop app".
- Test photos on a USB stick:
  - at least 3 sharp H&E photos (for example `frontend/e2e/fixtures/slide.jpg`, plus real eyepiece photos);
  - 1 deliberately **blurry** photo;
  - 1 file that is **not** an image (rename a `.txt` to `.jpg`).
- Optional: a phone with a USB-webcam app (shows up as `uvc:0`) or an RTSP camera app on the same Wi-Fi, plus
  the microscope adapter.
- A stopwatch (a phone is fine).

## Steps

Record every **⏱ time** and every **✅/❌** on the results sheet.

### A. Install (online or offline, doesn't matter)
1. **Windows:** run the `.exe`. SmartScreen warns because the app isn't signed yet: **More info → Run anyway**.
   Keep the default folder.
   **Linux:** `sudo apt install libfuse2` (Ubuntu 22.04 needs it for AppImages; once only), then
   `chmod +x "Pathology Triage-<version>.AppImage"` and double-click it.
   **macOS:** open the `.dmg`, drag the app to Applications, then right-click → **Open** → **Open**.
2. ✅ The app installs without errors. ⏱ Install time.

### B. First start
3. **Turn off Wi-Fi and unplug the network cable.** Everything from here on must work offline (TDD 1.2).
4. Open the app. A start-up screen says "Эрэмбэлэх системийг эхлүүлж байна…".
   ⏱ **First start**: time until the dashboard appears. The first start unpacks the engine, so up to about a minute is fine.
5. ✅ The dashboard is in **Mongolian**, and the header shows a **green** "Эрэмбэлэх систем ажиллаж байна".
6. Quit (**Ctrl+Q**, or **Cmd+Q** on macOS) and open it again. ⏱ **Second start** (should be clearly faster).

### C. Triage a slide
7. Click **Зураг илгээх**, choose a sharp photo, choose **Яаралтай**, then click **Хиймэл оюуны эрэмбэлэлтэд илгээх**.
   ⏱ **Upload → in worklist**: from the click until the slide appears in the worklist with a risk colour.
8. Open the slide. ✅ The photo and the **heatmap** show; the opacity slider goes 0–100%; zoom works.
   📝 Copy **"Хиймэл оюуны шинжилгээний хугацаа"** (AI inference time). TDD target: **< 1.5 s** on CPU.
9. Repeat 7–8 with two more photos. ✅ The worklist orders them by AI score. Switching **"Хиймэл оюуны эрсдэлээр
   эрэмбэлэх"** off puts Urgent first.
10. Open one slide → **Хянаж эхлэх** → **Хоргүй гэж тэмдэглэх** → confirm. ✅ It moves to the **Архив** tab.
11. Upload the **non-image** file. ✅ A clear error, and the app keeps working.
12. Upload the **blurry** photo. Note what happens. The blur gate is **off by default**: it is only active when the
    `TRIAGE_SHARPNESS` environment variable is set (backend README recommends `100`). Repeat this with it set
    to 100 and write down whether the photo is rejected with "Зураг хэт бүдэг байна…".

### D. Load and resources
13. Upload 5 photos quickly in a row. ✅ All of them end up in the worklist, and the app stays responsive.
14. Open Task Manager (Windows), System Monitor (Ubuntu) or Activity Monitor (macOS). 📝 **RAM** used by
    "Pathology Triage" + "triage-backend" when idle and during step 13. 📝 Peak **CPU %**. Note anything
    unusual, such as the fan at full speed or the PC getting hot (TDD 8.1: overheating risk).

### E. Camera (optional, if you have the phone setup)
15. **Микроскопын камер** → enter `uvc:0` (USB) or the phone's `rtsp://…` address → **Холбох**.
    ✅ The **live view** appears and moves smoothly enough to focus. 📝 How smooth (good / jerky / none).
16. **Бэлдмэлийн зураг авах**. ✅ A new slide is added and scored.
17. **Салгах**. ✅ The live view disappears.

### F. Robustness
18. Upload a photo and **immediately** close the app (or end its task in Task Manager) while it is analysing.
    Reopen it. ✅ The slide shows as **Алдаа гарсан** (failed); **Шинжилгээг дахин эхлүүлэх** scores it.
19. Quit the app. ✅ Task Manager / System Monitor shows **no** `triage-backend` process left running.
20. ✅ Switch to **EN**, quit and reopen: the app is still in English. Switch back to **МН**.

## Pass criteria

| Check | Pass |
|---|---|
| Installs and starts offline | Yes, no internet needed at any step |
| AI inference time (step 8) | < 1.5 s per slide (TDD 5.2) |
| Upload → in worklist (step 7) | ≤ 3 s target (TDD 8.2); report the real number either way |
| Second start (step 6) | ≤ 15 s |
| All ✅ in steps 5–20 | Every one passes, or has an issue filed |
| Leftover processes (step 19) | None |

## Where things are on each OS

| | Windows | Ubuntu | macOS |
|---|---|---|---|
| Patient data (database, images, heatmaps) | `%APPDATA%\Pathology Triage\data` | `~/.config/Pathology Triage/data` | `~/Library/Application Support/Pathology Triage/data` |
| Backend log (attach to issues) | `%APPDATA%\Pathology Triage\logs\backend.log` | `~/.config/Pathology Triage/logs/backend.log` | `~/Library/Logs/Pathology Triage/backend.log` |

`TRIAGE_DATA_DIR` moves the data folder (for example to a second disk). Uninstalling the app keeps the data folder.
Delete it by hand only when patient data may be destroyed.

## Results sheet

Copy this into the GitHub issue, one per machine:

```
Machine: <model>        OS: <Windows 11 / Ubuntu 22.04 / macOS …>
CPU: <model, cores>     RAM: <GB>     GPU: <none / integrated model>
Tester: <name>          Date: <yyyy-mm-dd>    App version: <x.y.z>

A  Install ok: ✅/❌            Install time: __ s
B  First start: __ s           Second start: __ s     Mongolian + green status: ✅/❌
C  Upload → worklist: __ s, __ s, __ s
   AI inference time: __ s, __ s, __ s
   Heatmap + slider + zoom: ✅/❌   Ordering + urgent toggle: ✅/❌   Review → archive: ✅/❌
   Non-image rejected: ✅/❌     Blurry photo (gate off): ______   (TRIAGE_SHARPNESS=100): ______
D  5 photos in a row ok: ✅/❌   RAM idle / busy: __ / __ MB   Peak CPU: __ %   Heat/fan: ______
E  Live view: good/jerky/none   Capture ok: ✅/❌   Disconnect ok: ✅/❌   (or: not tested)
F  Interrupted slide → failed → retry ok: ✅/❌   No leftover process: ✅/❌   Language kept: ✅/❌
Notes / problems:
```
