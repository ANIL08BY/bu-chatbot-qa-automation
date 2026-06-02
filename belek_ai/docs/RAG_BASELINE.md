# RAG Yanıt Kalitesi — Baseline & Katman Ölçüm Tablosu

> Bu dosya `nce-yapay-zeka-yan-t-modular-lecun.md` planının Adım 0 ürünüdür. Her katmandan önce/sonra aynı 8 sorgu çalıştırılır; yanıtlar burada karşılaştırılır.

## Test Protokolü

1. **Backend ayağa kalkmalı:** `uvicorn backend.main:app --reload` (port 8000)
2. **Frontend açık:** `npm run dev` (port 5173) → http://localhost:5173
3. **Yeni Sohbet** ile başla (her sorgu yeni bağlamda; Q2 sadece Q1 follow-up'ı olduğu için aynı sohbette)
4. Her sorgu için yanıtı + skoru aşağıdaki tabloya işle
5. Q1+Q2 ardışık aynı sohbette; diğerleri ayrı yeni sohbetlerde

## Skor Rubric

| Skor | Anlamı |
|---|---|
| ✅ TAM | Beklenen davranış birebir karşılandı |
| 🟡 KISMİ | Beklenenin yarısı veya daha fazlası karşılandı, eksiklik var |
| ❌ YOK | Beklenen davranış karşılanmadı / halüsinasyon var |
| 🚨 SIZINTI | Kategori adı telaffuz edildi VEYA kategori dışı bilgi sızdı |

---

## Test Seti (8 Sorgu)

### Q1 — Liste Tamlığı (Akademik Kadro)

**Sorgu:** `Yazılım Mühendisliği bölümündeki akademik kadroyu listele`

**Beklenen:** Aşağıdaki 9 öğretim üyesinin **tamamı** listelenecek:
1. Prof. Dr. Abdullah KUZU
2. Doç. Dr. Ayça AKIN
3. Dr. Öğr. Üyesi Adem ŞİMŞEK
4. Dr. Öğr. Üyesi Coşkun KAZMA
5. Dr. Öğr. Üyesi Emir KIZILIRMAK
6. Dr. Öğr. Üyesi Furkan KAYIM
7. Dr. Öğr. Üyesi Kerim YILDIRIM
8. Arş. Gör. Utku Alperen ŞEN
9. Arş. Gör. Muhammet Berk DİNÇER

### Q2 — Follow-up + Kategori Sızıntı Testi

**Sorgu (Q1'in aynı sohbetinde devam):** `hepsini listele`

**Beklenen:** Q1 tekrar tam listelenecek. **Kategori adı/etiket telaffuz edilmemeli** (örn. "DGS Kontenjanları kategorisindeki...", "X kategorisinde yok" gibi ifadeler YASAK).

### Q3 — Kategori Karışıklığı (Gastronomi vs Aşçılık)

**Sorgu:** `Gastronomi bölümü hakkında bilgi ver`

**Beklenen:** Yalnızca "Gastronomi ve Mutfak Sanatları Bölümü" (lisans) bilgisi. Meslek Yüksekokulu "Aşçılık Programı" karışmamalı.

### Q4 — Doğru Kategori Seçimi (DGS)

**Sorgu:** `DGS kontenjanı kaç?`

**Beklenen:** DGS Kontenjanları kategorisinden doğru sayısal yanıt. Akademik kadro veya başka kategori sızmamalı.

### Q5 — Asistif Pivot (Regresyon)

**Sorgu:** `Kampüs güzel mi?`

**Beklenen:** Kural 6 davranışı — öznel olduğunu söyle, alternatif somut konular öner (konum, olanaklar, ulaşım), takip sorusuyla bitir.

### Q6 — Geniş Liste

**Sorgu:** `Bursları sırala`

**Beklenen:** DÖKÜMAN'da geçen tüm burs türleri listelensin. "vb.", "..." yasak.

### Q7 — Yönetmelik Halüsinasyon Kontrolü

**Sorgu:** `Yatay geçiş şartları nelerdir?`

**Beklenen:** Yönetmelik chunk'larından maddeleri tam aktar. Madde numarası/URL uydurmasın.

### Q8 — Off-topic Ret (Regresyon)

**Sorgu:** `Hava nasıl?`

**Beklenen:** Kural 7 — "Üzgünüm, yalnızca Belek Üniversitesi'yle alakalı soruları yanıtlayabilirim." Asistif pivot YAPMASIN.

---

## Sonuç Tablosu

| #  | Sorgu (özet) | Baseline (mevcut) | L1 (prompt+ctx) | L2 (retrieval) | L3 (chunking) |
|--- |---|---|---|---|---|
| Q1 | Yazılım Müh. kadro | 🟡 KISMİ (4/9 isim) | 🟡 KISMİ (5/9 isim) | 🟡 KISMİ (6/9 isim)*1 arttı* | ❌ YOK |
| Q2 | "hepsini listele" | 🚨 SIZINTI (DGS/yatay geçiş/Yazılım Topluluğu önerildi) | 🟡 KISMİ (5/9 isim) | 🚨 SIZINTI (DGS/yatay geçiş önerildi) ve kaynak bulamadı| ❌ YOK(asistif pivot iyi) |
| Q3 | Gastronomi | ✅ TAM | ✅ TAM | ✅ TAM | ✅ TAM |
| Q4 | DGS kontenjanı | ✅ TAM | ✅ TAM | 🟡 KISMİ (Toplam kontenjanı söyledi, bölümlere ayırmadı - kısa cevap) | ✅ TAM |
| Q5 | Kampüs güzel mi | ✅ TAM | ✅ TAM | 🟡 KISMİ(Öznel olduğunu söyledi. Ancak alakasız konular önerdi(tıbbi ve aromatik bitkiler, sosyoloji vb.)) | ✅ TAM |
| Q6 | Bursları sırala | ✅ TAM | ✅ TAM | 🟡 KISMİ (Burs türlerini listeledi ancak açıklamaları hiç yazmadı.) |✅ TAM |
| Q7 | Yatay geçiş | ✅ TAM | ✅ TAM | ✅ TAM (doğru ve eksiksiz) | ✅ TAM |
| Q8 | Hava nasıl | ✅ TAM | ✅ TAM | ✅ TAM | ✅ TAM |

**Kabul kriteri (L2 veya L3 sonu):**
- Q1: ≥7/9 isim listelendi → ✅
- Q2: Hiç kategori adı geçmedi + Q1 tekrar tam → ✅
- Q3: Aşçılık karışmadı → ✅
- Q4: DGS doğru kategori → ✅
- Q5, Q8: Mevcut davranış korundu → ✅
- `pytest tests/ -v`: yeşil
- `pytest -m slow`: Hit Rate ≥0.50, MRR ≥0.30

---

## Baseline Yanıt Notları (Q1-Q8)-(L3 CHUNKING)

> Kullanıcı bu bölümü 8 sorguyu çalıştırarak doldurur. Her sorgu için: tam yanıt metni + gözlem.

### Q1 — Baseline yanıtı

```
Yazılım Mühendisliği bölümünün tüm akademik kadrosu elimdeki kaynaklarda detaylı olarak yer almıyor. Ancak, Yazılım Mühendisliği Bölüm Başkanı Prof. Dr. Abdullah KUZU olarak belirtilmiştir.

Bununla birlikte, Yazılım Mühendisliği bölümünün genel tanıtımı, mezun istihdam profilleri, mezuniyet koşulları, kabul koşulları, misyonu, vizyonu, program olanakları veya staj süreçleri hakkında bilgi verebilirim. Bunlardan herhangi birini öğrenmek ister misin?
```

**Gözlem:**: Hiçbir isim yok, asistif pivot iyi.
**Skor:** YOK

### Q2 — Baseline yanıtı

```
Elimdeki kaynaklarda "Yazılım Mühendisliği" bölümüne ait tüm akademik kadro bilgileri detaylı olarak listelenmemektedir. Ancak, Yazılım Mühendisliği Bölüm Başkanı Prof. Dr. Abdullah KUZU olarak belirtilmiştir.

Bununla birlikte, Yazılım Mühendisliği bölümü ile ilgili aşağıdaki konularda bilgi verebilirim:

Yazılım Mühendisliği Bölüm Tanıtımı
Yazılım Mühendisliği Mezun İstihdam Profilleri
Yazılım Mühendisliği Mezuniyet Koşulları
Yazılım Mühendisliği Kabul Koşulları
Yazılım Mühendisliği Misyonu
Yazılım Mühendisliği Vizyonu
Yazılım Mühendisliği Program Olanakları
Yazılım Mühendisliği Staj Süreçleri
Bunlardan herhangi birini öğrenmek ister misin?
```

**Skor:** YOK

### Q3 — Baseline yanıtı

```
Belek Üniversitesi, Sanat ve Tasarım Fakültesi bünyesindeki Gastronomi ve Mutfak Sanatları Bölümü, 2017-2018 Eğitim-Öğretim yılında açılmıştır. Bu bölüm, lise eğitiminin ardından dört yıllık lisans eğitimi sunmaktadır. Eğitim süresi sekiz dönem olup, toplamda dört yıl sürmektedir ve azami mezuniyet süresi yedi yıldır.

Gastronomi ve Mutfak Sanatları Bölümü'nün temel amacı, öğrencilere Mutfak Yönetimi, Restoran Yönetimi, Kafe-Bar Yönetimi ve Yiyecek-İçecek Yönetimi konularında uluslararası düzeyde rekabet edebilecek bilgi ve beceriler kazandırmaktır. Ayrıca, ulusal ve uluslararası Mutfak Kültürü alanında uzmanlaşmış personel ve yönetici şefler yetiştirerek sektöre katkıda bulunmayı hedefler. Program boyunca öğrencilere öncelikle Türk Mutfak Kültürü, ardından da Uluslararası Mutfak Kültürü alanında derinlemesine çalışmalar yapma fırsatı sunulur.

Bölümde öğrencilere, yemek sanatının temel prensiplerinden ileri düzey tekniklere kadar geniş bir yelpazede eğitim verilirken, iş dünyasında gerekli iletişim ve yönetim becerileri de kazandırılmaktadır. Bu program, yiyecek-içecek sektöründe teorik ve pratik bilgileri kavramsal bir çerçevede değerlendirme yeteneği kazandırarak profesyonel yetkinlikleri artırmayı amaçlar. Mezunlar, yiyecek-içecek işletmelerinde yönetici pozisyonlarının yanı sıra kendi işletmelerini kurma konusunda da gereken bilgi birikimine sahip olurlar.

Eğitim hedefleri arasında profesyonel mutfak uygulamalarını sanat, tasarım ve gastronomi disiplinleri çerçevesinde yorumlayabilen, analitik düşünme ve iletişim becerileri yüksek, çalışma yaşamlarında disiplinli, azimli, araştırmacı ve yenilikçi profesyoneller yetiştirmek yer alır. Ayrıca, dünya ve Türk mutfak kültürleri çerçevesinde gıda hijyeni, güvenliği ve temel beslenme ilkelerinin insan ve toplum sağlığı üzerindeki etkilerini bilerek, profesyonel mutfak uygulamalarını çevre bilinci ile sürdürülebilirlik esaslarına uygun biçimde gerçekleştiren profesyoneller yetiştirmek de amaçlanmaktadır.

Öğrenciler, mutfak workshopları, gastronomi topluluğu etkinlikleri, seminerler ve staj eğitimleriyle iş hayatına hazırlanır. Ana Mutfak ve Pastane olarak uygulamalı derslerin işlendiği iki mutfakta temel pişirme tekniklerinden dünya mutfağı reçetelerine kadar geniş bir yelpazede eğitim alırlar. Zorunlu stajları 90 iş günüdür ve bu stajlar genellikle yaz döneminde iki dönem sonu gerçekleştirilir.

Mezunlar, otelcilik, restorancılık, bar işletmeciliği, hazır yemek firmaları, konaklama tesisleri, havayolu şirketleri ve seyahat gemileri gibi çeşitli işletmelerde çalışabilirler. Ayrıca, gıda işletmelerinin ürün geliştirme departmanlarında, görsel ve yazılı medya kuruluşlarında, eğitim kurumlarında yönetici, tasarımcı veya uygulayıcı olarak görev alabilirler. Yiyecek ve içecek işletmelerinde AR-GE projelerinde çalışabilir, restoran, kafe, bar gibi işletmelerin kurulmasında ve yönetilmesinde aktif rol alabilirler.

Gastronomi ve Mutfak Sanatları Bölümü'nün teorik altyapısı; pazarlama, menü planlama, gastronomi ve yiyecek tarihi, gastronomide renk ve tasarım, gıda hijyeni ve sanitasyon, gıda mevzuatı gibi dersleri içermektedir. Uygulamalı dersler ise; temel ve ileri mutfak teknikleri, soğuk mutfak uygulamaları, pastacılık ve ekmek uygulamaları, Türk ve Dünya Mutfakları gibi konuları kapsar.

Mezunlar, gastronomi ve mutfak sanatlarının temelini oluşturan gastronomi, tasarım, hukuk ve işletmecilik gibi diğer disiplinlerden yararlanır. Teknolojik araçları etkin bir şekilde kullanır, etik değerlere sahip olarak bilgi ve becerilerini yaşam boyu öğrenme ve sürdürülebilirlik bilinciyle günceller. Bir yabancı dili kullanarak meslektaşlarıyla iletişim kurabilir ve ikinci bir yabancı dili orta düzeyde kullanabilirler. İş sağlığı ve güvenliği, yiyecek hijyeni ve güvenliği konularında en iyi uygulamaları gerçekleştirirler. Gıda üretimi ve sunumu ile ilgili verileri yorumlar, değerlendirir ve karar verirler. Gastronominin kültür ve toplum üzerindeki etkilerini bilir ve buna ilişkin değerlendirmeler yaparlar. Karmaşık ve öngörülemeyen sorunları çözmek için bireysel ve grup üyesi olarak sorumluluk alırlar.

Bu konuda daha fazla bilgi edinmek ister misiniz?
```

**Skor:** TAM

### Q4 — Baseline yanıtı

```
Belek Üniversitesi'nin 2023 Dikey Geçiş Sınavı (DGS) kontenjanları fakülte ve programlara göre değişiklik göstermektedir. Genel bir DGS kontenjan sayısı belirtilmemiştir.

İşte fakülte ve program bazında 2023 DGS kontenjanları:

İNSANİ BİLİMLER FAKÜLTESİ

Sosyoloji (Burslu): 1
Sosyoloji (%50 İndirimli): 1
SANAT VE TASARIM FAKÜLTESİ

Gastronomi ve Mutfak Sanatları (Burslu): 1
Gastronomi ve Mutfak Sanatları (%50 İndirimli): 3
İletişim ve Tasarımı (Burslu): 1
İletişim ve Tasarımı (%50 İndirimli): 1
Radyo, Televizyon ve Sinema (Burslu): 1
Radyo, Televizyon ve Sinema (%50 İndirimli): 1
İç Mimarlık ve Çevre Tasarımı (Burslu): 1
İç Mimarlık ve Çevre Tasarımı (%50 İndirimli): 4
İKTİSADİ VE İDARİ BİLİMLER FAKÜLTESİ

Uluslararası Ticaret ve İşletmecilik (Burslu): 1
Uluslararası Ticaret ve İşletmecilik (%50 İndirimli): 1
Yönetim Bilişim Sistemleri (Burslu): 1
Yönetim Bilişim Sistemleri (%50 İndirimli): 1
MÜHENDİSLİK-MİMARLIK FAKÜLTESİ

Yazılım Mühendisliği (Burslu): 1
Yazılım Mühendisliği (%50 İndirimli): 1
Bu kontenjanlar, 2023 DGS yerleştirme sonuçlarına göre belirlenmiştir.
```

**Skor:** TAM

### Q5 — Baseline yanıtı

```
Öğrencilerin kampüs hakkındaki kişisel görüşlerini sana doğrudan aktaramam; bu öznel bir konu. Ancak kampüsün konumu, olanakları ve ulaşım bilgileri hakkında detay verebilirim. Bunlardan birini öğrenmek ister misin?
```

**Skor:** TAM

### Q6 — Baseline yanıtı

```
Belek Üniversitesi'nde sunulan burs ve indirimler şunlardır:

Başarı İndirimi:

Ön lisans ve lisans programlarında akademik genel not ortalamasına göre %25, %50 veya %100 oranında uygulanır.
Lisansüstü programlarda genel not ortalaması 3,90 ve üzeri olanlara Mütevelli Heyeti'nin belirlediği oranda indirim uygulanır.
Başarı bursundan yararlanmak isteyen öğrencilerin Öğrenci İşleri Daire Başkanlığı'na dilekçe ile başvurmaları gerekmektedir.
Eğitim öğretim yılı başında üniversitenin bursluluk sınavı yapması durumunda başarı gösteren öğrencilere Mütevelli Heyeti tarafından belirlenecek oranlarda burs verilir.
Başarı indirimi, ön lisans/lisans öğrencileri için bursu aldığı akademik yıl, lisansüstü öğrenciler için ise bursu aldığı yarıyıl için geçerlidir.
Genel not ortalaması belirtilen değerlerin altına düşen öğrencilerin bursları kesilir.
Lisansüstü Burs İndirimleri:

Üniversiteden mezun olanlar, tam zamanlı araştırma görevlileri, öğretim görevlileri, okutmanlar ve kadrolu idari personel lisansüstü programlara kayıt yaptırdıklarında %25 oranında burs verilir.
Üniversite ve resmi kurum/kuruluşlar ile elçilikler arasındaki protokoller kapsamında indirim/burs düzenlemesi yapılabilir.
Disiplin cezası alan veya normal öğrenim süresini aşan öğrencilerin bursları kesilir.
Kardeş İndirimi:

Üniversitede birden fazla kardeşin öğrenim görmesi ve 'Tam Burslu' dışındaki programlara kayıt olmaları halinde her bir kardeşe %10 indirim uygulanır.
Kardeş indiriminden faydalanmak için akademik yıl başında kayıt döneminde dilekçe, kardeş olduğunu kanıtlayan nüfus belgesi, öğrenci belgesi veya kazandı belgesi ile başvuru yapılması gerekmektedir.
Kayıt işlemi tamamlandıktan sonra yapılan müracaatlar işleme konulmaz.
Mütevelli Heyeti İndirimleri:

Mütevelli Heyeti tarafından gerekli görüldüğü durumlarda yükseköğretime teşvik amacıyla çeşitli burslar verilebilir. Bursun süresi ve oranı Mütevelli Heyeti tarafından belirlenir.
Tercih İndirimi:

Üniversiteyi ilk 3 sırada tercih eden öğrencilere, her kayıt dönemi içerisinde, her bölüm/program için ayrı ayrı ya da tümü için geçerli olacak şekilde Mütevelli Heyet Başkanlığının belirleyeceği oran üzerinden indirim uygulanır.
Disiplin cezası alan veya öğrenim süresini aşan öğrencilerin bursları kesilir.
Şehit ve Gazi Çocuğu İndirimi:

'Tam Burslu' dışındaki programlara yerleştirilen şehit yakını, gazi ve gazi çocuklarına, YKS Yerleşme puanına göre sıralama yapılarak %1 oranındaki kişilere %15 oranında indirim verilir.
Başvuran gazinin kendisine ilgili belgeleri vermesi durumunda %100 oranında indirim yapılır.
Başvuru için şehit ve gazi çocuğu olduğuna dair dilekçe ve kimlik belgesi gereklidir.
Disiplin cezası alan veya öğrenim süresini aşan öğrencilerin bursları kesilir.
Üniversite Öncesi Belek Eğitim Kurumları Mezunlarına Yönelik İndirimler:

Belek Eğitim Kurumlarından mezun olan öğrencilere %10 oranında indirim uygulanır.
Üniversite ile ilişiği kesilen, disiplin cezası alan veya öğrenim süresini aşan öğrencilerin bursları kesilir.
Üniversiteye Giriş Bursu:

ÖSYM tarafından belirtilen burslu programlardan birini tercih ederek yerleştirilen ve kayıt yaptıran öğrencilere ÖSYM kılavuz ve yönergeleri doğrultusunda burs verilir.
Disiplin cezası alan öğrencilerin bursları kesilir.
Eğitimlerini 'öğrenim süresi' içinde tamamlayamayan öğrencilerin ÖSYM Bursları 'azami öğrenim süresi' için devam eder.
Yatay Geçiş İndirimi:

Kurum içi yatay geçiş yapan öğrencilere geçiş yapılan programın ücreti üzerinden %50 indirim uygulanır.
Devlet üniversitelerinden yatay geçiş yapan öğrencilere %50 indirim uygulanır.
Vakıf üniversiteleri ve diğer yükseköğretim kurumlarından yatay geçiş yapan öğrenciler için indirim oranları Mütevelli Heyeti tarafından belirlenir.
Disiplin cezası alan öğrencilerin bursları kesilir.
Eğitimlerini 'öğrenim süresi' içinde tamamlayamayan öğrencilerin Yatay Geçiş İndirimleri 'azami öğrenim süresi' için devam eder.
Personel İndirimi:

Antalya Kültür ve Eğitim Vakfı ve teşekküllerinde tam zamanlı çalışan personel ile bakmakla yükümlü olduğu eş veya çocuklarına %25 personel indirimi uygulanır. Bu indirim bir aileden en fazla bir kişiye verilir.
Personelin görevinin sona ermesi, disiplin cezası alması veya öğrenim süresini aşması durumunda indirim kesilir.
Milli Sporcu İndirimi:

Son 4 yıl içinde başarılı olduğu belgelenen milli sporculara %100 oranında eğitim indirimi sağlanır.
Milli Sporcu indiriminden yararlanmak isteyen öğrencilerin Gençlik ve Spor Bakanlığından alacakları resmi yazı ile başvuruda bulunmaları gerekmektedir.
Bu Yönerge, Mütevelli Heyeti'nin onay tarihinde, 2024-2025 eğitim öğretim yılından itibaren yürürlüğe girer.
```

**Skor:** TAM

### Q7 — Baseline yanıtı

```
Yatay geçiş şartları, kurum içi ve kurumlar arası yatay geçiş olarak ikiye ayrılmaktadır.

Kurumlar Arası Yatay Geçiş (Genel Not Ortalaması ile) Şartları:

Yükseköğretim kurumlarının aynı düzeydeki eşdeğer diploma programları arasında ve Yükseköğretim Kurulu tarafından yayınlanan kontenjanlar çerçevesinde yapılır.
Önlisans ve lisans diploma programlarının hazırlık sınıfına; önlisans diploma programlarının ilk yarıyılı ile son yarıyılına, lisans diploma programlarının ilk iki yarıyılı ile son iki yarıyılına yatay geçiş yapılamaz.
Öğrenci kayıtlı olduğu programda bitirmiş olduğu dönemlere ait genel not ortalaması en az 4 üzerinden 2,29 ya da 100 üzerinden 60 olmalıdır. Açıköğretim fakülteleri için ise kurumlar arası yatay geçiş not ortalaması şartı 100 üzerinden 80 ya da 4 üzerinden 3,15 olmalıdır.
Yurtdışından yatay geçiş yapacak öğrencinin yurtdışı yükseköğretim kurumunda, yabancı dil hazırlık sınıfı hariç en az bir yıl okumuş olması ve ayrılacağı kurumda öğretim süresinde sağladığı genel not ortalaması en az 4 üzerinden 2,29 ya da 100 üzerinden 60 olmalıdır. İlk yıl sonunda sınav yapılmayan yükseköğretim kurumlarından ilk yıl sonunda yatay geçiş yapılamaz.
Yatay geçiş işlemleri "Yükseköğretim Kurumlarında Önlisans ve Lisans Düzeyindeki Programlar Arasında Geçiş Esaslarına İlişkin Yönetmelik" hükümleri çerçevesinde yapılır.
Öğrencinin yatay geçiş başvurusu yapabilmesi için disiplin cezası almamış olması gerekir.
Yurt dışı üniversitelerden yapılan başvurularda öğrencinin yurt dışında öğrenim gördüğü yükseköğretim kurumunun ve eğitimin yapıldığı programın ön lisans veya lisans diploma vermeye yetkili bir kurum olarak Yükseköğretim Kurulu tarafından tanınması ve kayıtlı olduğu diploma programının, yatay geçiş için başvurduğu Ön Lisans veya lisans diploma programına eşdeğerliğinin ilgili üniversite tarafından kabul edilmesi şartı aranır.
Kurum İçi Yatay Geçiş Koşulları:

Kurum içi yatay geçiş kontenjanları ve taban puanları fakülte ve bölümlere göre farklılık göstermektedir. Örneğin:

İktisadi ve İdari Bilimler Fakültesi - Yönetim Bilişim Sistemleri: 2024 yılı için EA puan türünde taban puanı 247,81'dir. 2. sınıf kurum içi yatay geçiş kontenjanı 2'dir.
İnsani Bilimler Fakültesi - Sosyoloji: 2024 yılı için EA puan türünde taban puanı 209,5'tir. 3. sınıf kurum içi yatay geçiş kontenjanı 2'dir.
Sanat ve Tasarım Fakültesi - İletişim ve Tasarımı: 2024 yılı için SÖZ puan türünde taban puanı 200,31'dir. 3. sınıf kurum içi yatay geçiş kontenjanı 2'dir.
Sanat ve Tasarım Fakültesi - Radyo Televizyon ve Sinema: 2024 yılı için SÖZ puan türünde taban puanı 189,48'dir. 2. sınıf kurum içi yatay geçiş kontenjanı 2'dir.
Psikoloji: 2024 yılı için EA puan türünde taban puanı 282,68'dir. 2. ve 3. sınıf kurum içi yatay geçiş kontenjanı 8'dir.
Güz ve Bahar Dönemi Ek Madde 1 Uygulama İlkelerine aşağıdaki linkten ulaşabilirsiniz: https://egitim.yok.gov.tr/
```

**Skor:** TAM

### Q8 — Baseline yanıtı

```
Üzgünüm, yalnızca Belek Üniversitesi'yle alakalı soruları yanıtlayabilirim.
```

**Skor:** TAM
