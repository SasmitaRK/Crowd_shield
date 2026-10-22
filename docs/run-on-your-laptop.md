# Watch a camera all day, from your own computer

The hosted app only counts while its page is open in a browser. To watch a camera around the clock,
run the monitor on your own computer. It needs no browser, writes a log, and can alert your phone.

## 1. One-time set-up

```
git clone https://github.com/khushi-git-7/Crowd_shield.git
cd Crowd_shield
python -m venv .venv
.venv\Scripts\activate          (Windows)   or   source .venv/bin/activate   (Mac, Linux)
pip install -r requirements.txt
```

The first count downloads the counting model (about 100 MB) once. It needs about 3 GB of free memory.

## 2. Say which parts of the picture to watch

Copy `examples/zones.example.json` and edit it. Each zone is a box on the camera picture (fractions of
its width and height: left, top, right, bottom) and the number of people it holds comfortably. Risk
starts at 50% of that number (Moderate), 75% (High Risk) and 100% (Critical). If you know the floor
area, add `"area_m2"` to also see people per m².

## 3. Start it

```
python -m crowdshield.live_cli --source "rtsp://user:password@192.168.1.20/stream" --zones my_zones.json --interval 30 --log counts.csv --notify
```

- `--source` is an RTSP or HTTP(S) stream (HLS `.m3u8`, MJPEG), or a video file to try it out.
  A camera on your own network needs `CROWDSHIELD_ALLOW_PRIVATE_URLS=1` set first.
- `--interval` is seconds from one count to the next (the count itself takes a few seconds).
- `--log` adds a line per zone per count to a CSV you can open in Excel.
- `--notify` sends new High Risk and Critical alerts to Telegram and/or email, if you set
  `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, or `GMAIL_USER` and `GMAIL_APP_PASSWORD`, as environment
  variables. Each zone is announced once per level, then quiet for 10 minutes.
- Press Ctrl+C to stop. A bad frame or a dropped connection does not stop it; it tries again.

Try it with no camera first: `--source assets/samples/paris_saint_lazare.mp4 --once`.

## Test it with a real camera: use a phone

No CCTV to hand? An Android phone makes a real network camera, which is the honest way to field-test
the monitor (public webcams online are mostly gone, locked behind tokens, or not allowed to be re-used).

1. Install **IP Webcam** (by Pavel Khlebovich, free) and press **Start server**. It shows an address such
   as `http://192.168.1.7:8080`.
2. Put the phone somewhere steady and high, looking down at a busy spot: a college gate, a canteen queue, a
   market lane. Ask permission where you need it, and keep it short: the monitor never stores the video.
3. On a laptop on the **same Wi-Fi**:

```
set CROWDSHIELD_ALLOW_PRIVATE_URLS=1            (Windows; on Mac or Linux: export CROWDSHIELD_ALLOW_PRIVATE_URLS=1)
python -m crowdshield.live_cli --source http://192.168.1.7:8080/video --zones my_zones.json --interval 30 --log field_test.csv
```

   Or run the app itself (`streamlit run main.py`), open **Live feed**, choose **Stream URL** and paste
   `http://192.168.1.7:8080/video`.
4. Count the people in a few of the same moments by hand and compare them with `field_test.csv`. That
   comparison is a real field result you can quote.

## What it is not

It looks at one picture per interval; it is not video-rate tracking. It does not recognise anyone: it
counts heads. It is a decision aid for trained staff, not a safety system.
