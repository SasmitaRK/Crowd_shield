# India crowd test set

105 photos of crowds in India, chosen to cover the places Crowd Shield is meant for:

- **Pilgrimages and melas:** Kumbh Mela (Prayagraj, Nashik), Gangasagar, Matua Mahamela.
- **Festivals:**
  - Ganesh Chaturthi (Mumbai), Durga Puja and Chhath (Kolkata), Holi (Howrah), Onam
    (Thiruvananthapuram), Attukal Pongala, Thrissur, Bonalu (Hyderabad), Jallikattu, Maha Shivaratri
    (Thanjavur).
  - Madurai's Chithirai festival and Meenakshi Temple processions.
- **Temples and shrines:** Golden Temple (Amritsar), the Jagannath Temple queue (Puri), Sabarimala, Rath Yatra.
- **Stations:** Mumbai (Bandra and others), Kanpur, Howrah metro, Thane, Dum Dum.
- **Streets and markets:** Chennai's T. Nagar, Kolkata, Bengaluru, Hyderabad (Charminar), Delhi, Mumbai.
- **Stadiums, ghats, beaches and rallies:** Eden Gardens, Motera, the Varanasi ghats, Puri beach,
  the Nehru Trophy boat race.

The photos test whether Crowd Shield's counter, trained on Chinese street and crowd photos
(ShanghaiTech), works on the crowds it was built for. They are **only ever used for testing,
never for training**, so the result stays honest.

Every photo is freely licensed on Wikimedia Commons (CC BY, CC BY-SA, CC0 or public domain).
`sources.csv` lists each one's title, photographer, licence and source page. The images here
were resized to at most 1920 px wide. Photos under CC BY-SA keep that licence.

## Labels

- `predictions/` holds the model's suggested head points for each photo.
- `labels.json` holds the hand-checked labels. Each photo's suggested points were loaded into
  `tools/annotate_heads.html`, and a person added missed heads, removed wrong points and marked
  **ignore zones** over people too small or blurry to mark one by one. Ignore zones are left out
  of both the true count and the model's count.
- **Status:** 10 photos are hand-checked (IN_01, 03, 05, 06, 08, 12, 14, 15, 19, 21). The rest
  are being labelled in batches, and each batch is audited with zoomed crops before it counts.

`data/india_negatives/` holds 23 photos of empty Indian railway tracks (true count 0), used
to study the track-gravel false counts.
