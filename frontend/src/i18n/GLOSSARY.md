# English ↔ Mongolian glossary

> **Status: needs review by a Mongolian-speaking pathologist.** These terms were drafted for the
> first bilingual release and have not yet been checked by a clinician. Until they are, treat the
> Mongolian medical wording as provisional. Record the reviewer's name and date here when done.

Use these terms consistently in `locales/mn/*.json`. If a term changes here, change it everywhere.

## Workflow and UI

| English | Mongolian | Notes |
| --- | --- | --- |
| AI | хиймэл оюун (ХО) | "ХО" only in tight column headers |
| triage / triage queue | эрэмбэлэлт / эрэмбэлэлтийн дараалал | |
| urgency score | яаралтай байдлын оноо | |
| high / moderate / low risk | өндөр / дунд / бага эрсдэл | AI risk flag (codes `critical` / `high` / `routine`) |
| clinical request: routine / urgent | эмнэлзүйн хүсэлт: энгийн / яаралтай | the referring clinic's indication |
| case | тохиолдол | |
| patient | өвчтөн | |
| specimen | сорьц | |
| slide | бэлдмэл | |
| clinic | эмнэлэг | |
| worklist / priority worklist | ажлын жагсаалт / эрэмбэлсэн ажлын жагсаалт | |
| under review | хянаж байгаа | slide state `under_review` |
| reviewed & archived | хянаж, архивласан | slide state `archived` |
| start review | хянаж эхлэх | |
| manual priority | гараар өгсөн эрэмбэ | `priority_override` |
| anonymous patient code | өвчтөний нэргүй код | salted hash of the patient ID |
| hotspot | голомт | outlined high-probability area on the heatmap |
| prioritisation assistant, not a diagnostic engine | эрэмбэлэх туслах хэрэгсэл, оношлох систем биш | TDD 8.1 warning |
| pathologist | эмгэг судлаач | |
| reviewer | хянагч эмч | |
| sign out (a case) | хаах | finalises the review and leaves the active queue |
| reopen | дахин нээх | |
| re-assign priority | эрэмбийг өөрчлөх | |
| awaiting review | хяналт хүлээж буй | |
| retake photo | дахин зураг авах | |
| stitch (photos) | нийлүүлэх | |
| heatmap | дулааны зураг | |
| model card / About the AI | загварын карт / Хиймэл оюуны тухай | generated model description page |
| distillation (teacher → student) | нэрмэл загвар (багш → сурагч) | Hibou-B foundation model → MobileNetV3-Small |
| foundation model | суурь загвар | large pretrained model used as distillation teacher |
| AUC | AUC | area under the ROC curve, patch/slide separation |
| tissue map | эдийн зураглал | |
| tile (224 px square) | хавтанцар | |
| eyepiece | окуляр | |
| focus | фокус | |
| resolution | нягтрал | |
| calibration / calibrated setup | калибровк / калибровк хийсэн тохиргоо | stage-micrometer µm/px per microscope + phone |
| objective (10x / 20x / 40x) | объектив | microscope objective; µm/px scales with its power |
| stage micrometer | тайзны микрометр | printed-scale slide for calibration |
| magnification (µm/px) | өсгөлт (мкм/пиксел) | model training scale is 0.42 µm/px |
| H&E staining | H&E будалт | |

## Review decisions

| English | Mongolian |
| --- | --- |
| Confirm malignancy | Хорт хавдрыг батлах |
| Mark benign | Хоргүй гэж тэмдэглэх |
| Request formal biopsy | Албан ёсны биопси хүсэх |
| diagnosis | онош |

## Tissue and cells

| English | Mongolian |
| --- | --- |
| tumor | хавдар |
| malignant / malignancy | хорт / хорт хавдар |
| benign | хоргүй |
| tumor epithelium | хавдрын хучуур эд |
| adenocarcinoma | аденокарцинома |
| squamous cell carcinoma | хавтгай эсийн хорт хавдар |
| hepatocellular carcinoma (HCC) | элэгний эсийн хорт хавдар (ГЦК) |
| necrosis | үхжил |
| debris | задрал |
| normal mucosa | хэвийн салст бүрхүүл |
| stroma | строма |
| smooth muscle | гөлгөр булчин |
| mucus / mucin | салс / муцин |
| lymphocytes | лимфоцит |
| adipose | өөхөн эд |
| fibrosis | фиброз |
| steatosis | өөхлөлт |
| inflammation | үрэвсэл |
| bile duct reaction | цөсний сувгийн урвал |
| gland | булчирхай |
| crypt | крипт |
| goblet cell | бокал эс |
| invasion | нэвчилт |
| nucleus / nuclei | бөөм |
| nucleolus | бөөмцөг |
| neoplastic | хавдрын (неопластик) |
| connective tissue | холбогч эд |
| portal tract | портал зам |
| alveoli | цулцан |
