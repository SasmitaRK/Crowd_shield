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

Suggested points now exist for all 105 photos. The other 95 are split into five batches by how
many points the model suggests, smallest first, so the quick ones come first:

| Batch | Photos | Suggested points per photo | Photos |
|---|---:|---|---|
| 1 | 19 | 14–57 | IN_11, IN_18, IN_31, IN_33, IN_34, IN_35, IN_47, IN_61, IN_67, IN_75, IN_77, IN_78, IN_79, IN_80, IN_86, IN_87, IN_99, IN_104, IN_105 |
| 2 | 19 | 62–109 | IN_29, IN_36, IN_38, IN_45, IN_46, IN_48, IN_51, IN_58, IN_63, IN_66, IN_68, IN_81, IN_83, IN_85, IN_88, IN_93, IN_94, IN_96, IN_97 |
| 3 | 19 | 118–183 | IN_24, IN_30, IN_41, IN_43, IN_44, IN_50, IN_55, IN_59, IN_60, IN_69, IN_70, IN_72, IN_74, IN_76, IN_84, IN_89, IN_92, IN_98, IN_103 |
| 4 | 19 | 204–509 | IN_07, IN_20, IN_23, IN_25, IN_27, IN_32, IN_37, IN_49, IN_52, IN_54, IN_56, IN_64, IN_65, IN_73, IN_90, IN_91, IN_95, IN_100, IN_102 |
| 5 | 19 | 571–9112 | IN_02, IN_04, IN_09, IN_10, IN_13, IN_16, IN_17, IN_22, IN_26, IN_28, IN_39, IN_40, IN_42, IN_53, IN_57, IN_62, IN_71, IN_82, IN_101 |

`data/india_negatives/` holds 23 photos of empty Indian railway tracks (true count 0), used
to study the track-gravel false counts.
