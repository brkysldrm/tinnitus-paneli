from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import json
import datetime

app = Flask(__name__)
app.secret_key = 'gizli_anahtar'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)

# MODELLER
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20))  # 'admin', 'doktor', 'hasta'
    name = db.Column(db.String(100))

class PatientDoctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hasta_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    doktor_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Anket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(100), nullable=False)
    sorular = db.relationship('Soru', backref='anket', cascade='all, delete-orphan')

class Soru(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    anket_id = db.Column(db.Integer, db.ForeignKey('anket.id'), nullable=False)
    metin = db.Column(db.String(300), nullable=False)
    tip = db.Column(db.String(50), default='text')  # 'text', 'choice', 'multi_choice'
    secenekler = db.Column(db.Text)
    sira = db.Column(db.Integer, default=0)  # ❗️Eklendi


class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hasta_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    anket_id = db.Column(db.Integer, db.ForeignKey('anket.id'))
    cevaplar = db.Column(db.Text)
    tarih = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class OdyolojikBilgi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hasta_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    doktor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    tarih = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    notlar = db.Column(db.Text)

    # Saf Ses (dB HL)
    sag_hava = db.Column(db.JSON)     # {'125': val, '250': val, ...}
    sol_hava = db.Column(db.JSON)
    sag_kemik = db.Column(db.JSON)
    sol_kemik = db.Column(db.JSON)

    # Konuşma Odiyometrisi
    srt_sag = db.Column(db.String(20))
    srt_sol = db.Column(db.String(20))
    mcl_sag = db.Column(db.String(20))
    mcl_sol = db.Column(db.String(20))
    sds_sag = db.Column(db.String(20))
    sds_sol = db.Column(db.String(20))
    ucl_sag = db.Column(db.String(20))
    ucl_sol = db.Column(db.String(20))

    # Eşleme / Maskeleme
    frekans_esleme_sag = db.Column(db.String(100))
    frekans_esleme_sol = db.Column(db.String(100))
    gurluk_esleme_sag = db.Column(db.String(100))
    gurluk_esleme_sol = db.Column(db.String(100))
    minimum_maskeleme_sag = db.Column(db.String(100))
    minimum_maskeleme_sol = db.Column(db.String(100))
    reziduel_inhibisyon_sag = db.Column(db.String(100))
    reziduel_inhibisyon_sol = db.Column(db.String(100))

# LOGIN YÜKLEYİCİ
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# GİRİŞ / ÇIKIŞ
@app.route('/', methods=['GET', 'POST'])
def login():
    hata = None
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(f'/{user.role}')
        else:
            hata = "❌ Hatalı kullanıcı adı veya şifre"
    return render_template('login.html', hata=hata)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')

# ADMIN PANELİ
@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        return redirect('/')

    doktorlar = User.query.filter_by(role='doktor').all()
    hastalar = User.query.filter_by(role='hasta').all()
    anketler = Anket.query.all()
    iliskiler = PatientDoctor.query.all()

    doktor_dict = {doktor.id: doktor for doktor in doktorlar}
    hasta_doktor_map = {}
    for iliski in iliskiler:
        doktor = doktor_dict.get(iliski.doktor_id)
        if doktor:
            hasta_doktor_map.setdefault(iliski.hasta_id, []).append(doktor)

    return render_template(
        'admin_panel.html',
        user=current_user,
        doktorlar=doktorlar,
        hastalar=hastalar,
        anketler=anketler,
        hasta_doktor_iliskileri=iliskiler,
        hasta_doktor_map=hasta_doktor_map
    )

@app.route('/add_doctor', methods=['POST'])
@login_required
def add_doctor():
    if current_user.role != 'admin':
        return redirect('/')

    email = request.form['email']
    if User.query.filter_by(email=email).first():
        flash("❌ Bu e-posta adresi zaten kayıtlı.", "danger")
        return redirect('/admin')

    new_user = User(
        name=request.form['name'],
        email=email,
        password=request.form['password'],
        role='doktor'
    )
    db.session.add(new_user)
    db.session.commit()
    flash("✅ Doktor başarıyla eklendi.", "success")
    return redirect('/admin')


@app.route('/add_patient', methods=['POST'])
@login_required
def add_patient():
    if current_user.role != 'admin':
        return redirect('/')

    email = request.form['email']
    if User.query.filter_by(email=email).first():
        flash("❌ Bu e-posta adresi zaten kayıtlı.", "danger")
        return redirect('/admin')

    new_user = User(
        name=request.form['name'],
        email=email,
        password=request.form['password'],
        role='hasta'
    )
    db.session.add(new_user)
    db.session.commit()

    doktor_ids = request.form.getlist('doktor_ids')
    for doktor_id in doktor_ids:
        relation = PatientDoctor(hasta_id=new_user.id, doktor_id=doktor_id)
        db.session.add(relation)
    db.session.commit()

    flash("✅ Hasta başarıyla eklendi.", "success")
    return redirect('/admin')

@app.route('/admin/anket_yeni', methods=['POST'])
@login_required
def anket_yeni():
    if current_user.role != 'admin':
        return redirect('/')

    baslik = request.form.get('baslik')
    yeni_anket = Anket(baslik=baslik)
    db.session.add(yeni_anket)
    db.session.flush()  # Anket ID'sini hemen almak için

    index = 0
    while True:
        metin = request.form.get(f"soru_metin_{index}")
        if not metin:
            break
        tip = request.form.get(f"soru_tip_{index}")
        secenekler = request.form.get(f"soru_secenek_{index}") if tip in ['choice', 'multi_choice'] else None

        soru = Soru(
            anket_id=yeni_anket.id,
            metin=metin,
            tip=tip,
            secenekler=secenekler
        )
        db.session.add(soru)
        index += 1

    db.session.commit()
    flash("✅ Yeni anket başarıyla oluşturuldu.", "success")
    return redirect('/admin')


@app.route('/admin/kullanici_guncelle/<int:user_id>', methods=['POST'])
@login_required
def kullanici_guncelle(user_id):
    if current_user.role != 'admin':
        return redirect('/')
    user = User.query.get_or_404(user_id)
    user.name = request.form['name']
    user.email = request.form['email']
    user.password = request.form['password']
    db.session.commit()
    return redirect('/admin')

@app.route('/admin/kullanici_sil/<int:user_id>', methods=['POST'])
@login_required
def kullanici_sil(user_id):
    if current_user.role != 'admin':
        return redirect('/')
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect('/admin')

@app.route('/admin/anket_sil/<int:anket_id>', methods=['POST'])
@login_required
def anket_sil(anket_id):
    if current_user.role != 'admin':
        return redirect('/')
    anket = Anket.query.get_or_404(anket_id)
    db.session.delete(anket)
    db.session.commit()
    return redirect('/admin')

@app.route('/admin/hasta_doktor_guncelle/<int:hasta_id>', methods=['POST'])
@login_required
def hasta_doktor_guncelle(hasta_id):
    if current_user.role != 'admin':
        return redirect('/')
    PatientDoctor.query.filter_by(hasta_id=hasta_id).delete()
    doktor_idler = request.form.getlist('doktor_ids')
    for doktor_id in doktor_idler:
        iliski = PatientDoctor(hasta_id=hasta_id, doktor_id=doktor_id)
        db.session.add(iliski)
    db.session.commit()
    return redirect('/admin')

# ✅ DOKTOR PANELİ VE HASTA EKLEME
@app.route('/doktor')
@login_required
def doktor_panel():
    if current_user.role != 'doktor':
        return redirect('/')
    hasta_iliski = PatientDoctor.query.filter_by(doktor_id=current_user.id).all()
    hasta_ids = [h.hasta_id for h in hasta_iliski]
    hastalar = User.query.filter(User.id.in_(hasta_ids)).all()
    return render_template('doktor_panel.html', user=current_user, hastalar=hastalar)

@app.route('/doktor/hasta_ekle', methods=['POST'])
@login_required
def doktor_hasta_ekle():
    if current_user.role != 'doktor':
        return redirect('/')
    yeni_hasta = User(
        name=request.form['name'],
        email=request.form['email'],
        password=request.form['password'],
        role='hasta'
    )
    db.session.add(yeni_hasta)
    db.session.commit()

    iliski = PatientDoctor(hasta_id=yeni_hasta.id, doktor_id=current_user.id)
    db.session.add(iliski)
    db.session.commit()

    flash("✅ Yeni hasta başarıyla eklendi.", "success")
    return redirect('/doktor')

@app.route('/hasta_anketleri/<int:hasta_id>')
@login_required
def hasta_anketleri(hasta_id):
    if current_user.role != 'doktor':
        return redirect('/')
    
    hasta_kayit = PatientDoctor.query.filter_by(doktor_id=current_user.id, hasta_id=hasta_id).first()
    if not hasta_kayit:
        return "Bu hastaya erişim yetkiniz yok.", 403

    hasta = User.query.get(hasta_id)
    anketler = Survey.query.filter_by(hasta_id=hasta_id).order_by(Survey.tarih.desc()).all()
    odyolojik_bilgiler = OdyolojikBilgi.query.filter_by(hasta_id=hasta_id).order_by(OdyolojikBilgi.tarih.desc()).all()

    return render_template(
        'hasta_anketleri.html',
        hasta=hasta,
        anketler=anketler,
        odyolojik_bilgiler=odyolojik_bilgiler
    )
@app.route('/hasta')
@login_required
def hasta_panel():
    if current_user.role != 'hasta':
        return redirect('/')

    anketler = Anket.query.all()
    yapilan_anketler = Survey.query.filter_by(hasta_id=current_user.id).order_by(Survey.tarih.desc()).all()
    
    gecmis_anketler = []

    for kayit in yapilan_anketler:
        anket = Anket.query.get(kayit.anket_id)
        sorular = Soru.query.filter_by(anket_id=anket.id).all()
        cevaplar = json.loads(kayit.cevaplar)

        icerik = []
        for soru in sorular:
            cevap = cevaplar.get(str(soru.id), "")
            if isinstance(cevap, list):
                cevap = ", ".join(cevap)
            icerik.append({"soru": soru.metin, "cevap": cevap})

        # THI puanı varsa al
        thi_puani = cevaplar.get("_toplam_thi_puani", None)

        gecmis_anketler.append({
            "anket_adi": anket.baslik,
            "tarih": kayit.tarih,
            "icerik": icerik,
            "puan": thi_puani
        })

    return render_template("hasta_panel.html", user=current_user, anketler=anketler, gecmis_anketler=gecmis_anketler)

@app.route('/doktor/hasta/<int:hasta_id>/anketler')
@login_required
def doktor_hasta_anketleri(hasta_id):
    if current_user.role != 'doktor':
        return redirect('/')

    hasta = User.query.get_or_404(hasta_id)

    # Doktor-hasta ilişkisini kontrol et
    if not PatientDoctor.query.filter_by(hasta_id=hasta_id, doktor_id=current_user.id).first():
        return "Bu hastaya erişim yetkiniz yok.", 403

    yapilan_anketler = Survey.query.filter_by(hasta_id=hasta.id).order_by(Survey.tarih.desc()).all()
    odyolojik_bilgiler = OdyolojikBilgi.query.filter_by(hasta_id=hasta.id).order_by(OdyolojikBilgi.tarih.desc()).all()  # 👈 EKLENDİ

    anket_listesi = []
    for kayit in yapilan_anketler:
        anket = Anket.query.get(kayit.anket_id)
        if not anket:
            continue

        sorular = Soru.query.filter_by(anket_id=anket.id).all()
        try:
            cevaplar = json.loads(kayit.cevaplar or '{}')
        except Exception as e:
            cevaplar = {}

        icerik = []
        for soru in sorular:
            cev = cevaplar.get(str(soru.id), "")
            if isinstance(cev, list):
                cev = ", ".join(cev)
            icerik.append({"soru": soru.metin, "cevap": cev})

        thi_puan = cevaplar.get("_toplam_thi_puani", None)

        if any(i["cevap"].strip() for i in icerik):
            anket_listesi.append({
                "anket_adi": anket.baslik,
                "tarih": kayit.tarih,
                "icerik": icerik,
                "puan": thi_puan
            })

    return render_template(
        "doktor_hasta_anketleri.html",
        hasta=hasta,
        anketler=anket_listesi,
        odyolojik_bilgiler=odyolojik_bilgiler  # 👈 EKLENDİ
    )

@app.route('/anket_doldur/<int:anket_id>', methods=['GET', 'POST'])
@login_required
def anket_doldur(anket_id):
    if current_user.role != 'hasta':
        return redirect('/')

    anket = Anket.query.get_or_404(anket_id)
    sorular = anket.sorular

    if request.method == 'POST':
        cevaplar = {}
        thi_puan = 0  # 🔵 THI puanı başlat

        puanlama = {  # 🔵 THI cevap puanları
            "Evet": 4,
            "Bazen": 2,
            "Hayır": 0
        }

        for soru in sorular:
            if soru.tip == "multi_choice":
                secimler = request.form.getlist(f"soru_{soru.id}_checkbox")
                cevaplar[str(soru.id)] = secimler
            else:
                cevap = request.form.get(f"soru_{soru.id}")
                cevaplar[str(soru.id)] = cevap

                # 🔵 Eğer bu anket THI ise puanı hesapla
                if anket.baslik == "Tinnitus Handicap Inventory (THI)":
                    thi_puan += puanlama.get(cevap, 0)

        # 🔵 Puanı cevabın içine ekle
        if anket.baslik == "Tinnitus Handicap Inventory (THI)":
            cevaplar["_toplam_thi_puani"] = thi_puan

        kayit = Survey(
            hasta_id=current_user.id,
            anket_id=anket.id,
            cevaplar=json.dumps(cevaplar)
        )
        db.session.add(kayit)
        db.session.commit()

        return redirect('/hasta')

    return render_template('anket_doldur.html', anket=anket, sorular=sorular)

@app.route('/admin/anket/<int:anket_id>', methods=['GET', 'POST'])
@login_required
def anket_duzenle(anket_id):
    if current_user.role != 'admin':
        return redirect('/')

    anket = Anket.query.get_or_404(anket_id)
    sorular = Soru.query.filter_by(anket_id=anket.id).order_by(Soru.sira.asc()).all()

    if request.method == 'POST':
        for soru in sorular:
            soru.metin = request.form.get(f"metin_{soru.id}", soru.metin)
            soru.tip = request.form.get(f"tip_{soru.id}", soru.tip)
            soru.secenekler = request.form.get(f"secenekler_{soru.id}", soru.secenekler)
            try:
                soru.sira = int(request.form.get(f"sira_{soru.id}", soru.sira))
            except (ValueError, TypeError):
                soru.sira = soru.sira or 0

        # Yeni soru ekleme
        yeni_metin = request.form.get("yeni_metin")
        if yeni_metin:
            yeni_tip = request.form.get("yeni_tip", "text")
            yeni_secenekler = request.form.get("yeni_secenekler", "")
            try:
                yeni_sira = int(request.form.get("yeni_sira"))
            except (ValueError, TypeError):
                yeni_sira = None

            if yeni_sira is None:
                max_sira = db.session.query(db.func.max(Soru.sira)).filter_by(anket_id=anket.id).scalar() or 0
                yeni_sira = max_sira + 1

            yeni_soru = Soru(
                anket_id=anket.id,
                metin=yeni_metin,
                tip=yeni_tip,
                secenekler=yeni_secenekler,
                sira=yeni_sira
            )
            db.session.add(yeni_soru)

        db.session.commit()
        flash("✅ Güncellemeler kaydedildi.", "success")
        return redirect(url_for("anket_duzenle", anket_id=anket.id))

    return render_template("anket_duzenle.html", anket=anket, sorular=sorular)

@app.route('/doktor/odyoloji/<int:hasta_id>', methods=['GET', 'POST'])
@login_required
def odyolojik_bilgi_ekle(hasta_id):
    if current_user.role != 'doktor':
        return redirect('/')

    hasta = User.query.get_or_404(hasta_id)
    if not PatientDoctor.query.filter_by(hasta_id=hasta_id, doktor_id=current_user.id).first():
        return "Bu hastaya erişim yetkiniz yok.", 403

    if request.method == 'POST':
        frekanslar = ["125", "250", "500", "1000", "2000", "4000", "6000", "8000"]
        def get_json(kanal):
            return {f: request.form.get(f"{kanal}_{f}") for f in frekanslar}

        bilgi = OdyolojikBilgi(
            hasta_id=hasta_id,
            doktor_id=current_user.id,
            notlar=request.form.get("notlar"),

            # Saf Ses
            sag_hava=get_json("sag_hava"),
            sol_hava=get_json("sol_hava"),
            sag_kemik=get_json("sag_kemik"),
            sol_kemik=get_json("sol_kemik"),

            # Konuşma
            srt_sag=request.form.get("srt_sag"),
            srt_sol=request.form.get("srt_sol"),
            mcl_sag=request.form.get("mcl_sag"),
            mcl_sol=request.form.get("mcl_sol"),
            sds_sag=request.form.get("sds_sag"),
            sds_sol=request.form.get("sds_sol"),
            ucl_sag=request.form.get("ucl_sag"),
            ucl_sol=request.form.get("ucl_sol"),

            # Eşleme
            frekans_esleme_sag=request.form.get("frekans_esleme_sag"),
            frekans_esleme_sol=request.form.get("frekans_esleme_sol"),
            gurluk_esleme_sag=request.form.get("gurluk_esleme_sag"),
            gurluk_esleme_sol=request.form.get("gurluk_esleme_sol"),
            minimum_maskeleme_sag=request.form.get("minimum_maskeleme_sag"),
            minimum_maskeleme_sol=request.form.get("minimum_maskeleme_sol"),
            reziduel_inhibisyon_sag=request.form.get("reziduel_inhibisyon_sag"),
            reziduel_inhibisyon_sol=request.form.get("reziduel_inhibisyon_sol"),
        )
        db.session.add(bilgi)
        db.session.commit()
        flash("✅ Odyolojik bilgi başarıyla kaydedildi.", "success")
        return redirect('/doktor')

    # 👇 GET için form sayfasını döndür
    return render_template("odyolojik_bilgi_form.html", hasta=hasta)


@app.route('/admin/soru_sil/<int:soru_id>', methods=['POST'])
@login_required
def soru_sil(soru_id):
    if current_user.role != 'admin':
        return redirect('/')
    soru = Soru.query.get_or_404(soru_id)
    anket_id = soru.anket_id
    db.session.delete(soru)
    db.session.commit()
    return redirect(f"/admin/anket/{anket_id}")

def create_default_surveys():
    # DEMOGRAFİK BİLGİLER
    if not Anket.query.filter_by(baslik="Demografik Bilgiler").first():
        anket = Anket(baslik="Demografik Bilgiler")
        db.session.add(anket)
        db.session.flush()

        sorular = [
            {"metin": "Yaşınız kaçtır?", "tip": "choice", "secenekler": "18–29,30–44,45–60,61 ve üzeri"},
            {"metin": "Cinsiyetiniz nedir?", "tip": "choice", "secenekler": "Kadın,Erkek,Belirtmek istemiyorum"},
            {"metin": "Eğitim durumunuz nedir?", "tip": "choice", "secenekler": "İlkokul,Ortaokul,Lise,Üniversite,Yüksek lisans ve üzeri"},
            {"metin": "Medeni durumunuz nedir?", "tip": "choice", "secenekler": "Bekar,Evli,Boşanmış,Dul"},
            {"metin": "Çalışma durumunuz nedir? (Birden fazla seçenek işaretleyebilirsiniz)", "tip": "multi_choice", "secenekler": "Tam zamanlı çalışıyorum,Yarı zamanlı çalışıyorum,Emekliyim,İşsizim,Öğrenciyim"},
            {"metin": "Meslek grubunuzu aşağıdakilerden seçiniz (Birden fazla seçenek işaretleyebilirsiniz)", "tip": "multi_choice", "secenekler": "Ofis/memur,Fabrika/teknik/işçi,Sağlık sektörü,Eğitim sektörü,Müzik/sanat,Diğer"},
            {"metin": "Çalışma ortamınızda yada günlük yaşamınızda gürültü maruziyeti hakkında nasıl bir durumdasınız?", "tip": "choice", "secenekler": "Sürekli yüksek seviyede gürültü var,Zaman zaman gürültüye maruz kalıyorum,Genellikle sessiz bir ortam var,Gürültüye hiç maruz kalmıyorum,Diğer"},
            {"metin": "Yaşadığınız yerleşim yeri nedir?", "tip": "choice", "secenekler": "Köy,İlçe/Kasaba,İl"},
            {"metin": "Sigara kullanıyor musunuz?", "tip": "choice", "secenekler": "Evet/düzenli kullanıyorum,Evet/ara sıra kullanıyorum,Hayır/kullanmıyorum,Eskiden kullanıyordum, bıraktım"},
            {"metin": "Alkol kullanıyor musunuz?", "tip": "choice", "secenekler": "Evet/düzenli kullanıyorum,Evet/ara sıra kullanıyorum,Hayır/kullanmıyorum,Eskiden kullanıyordum/bıraktım"},
            {"metin": "Aşağıdaki kronik hastalıklardan herhangi birine sahip misiniz? (Birden fazla seçenek işaretleyebilirsiniz)", "tip": "multi_choice", "secenekler": "Yüksek tansiyon,Şeker hastalığı (Diyabet),Tiroid bozukluğu,Kalp hastalığı,Depresyon,Anksiyete bozukluğu,Kulak hastalıkları,Başka bir hastalık yok,Diğer"},
            {"metin": "İşitme cihazı kullanıyor musunuz?", "tip": "choice", "secenekler": "Hayır,Evet/0-6 aydır,Evet/ 6-12 aydır,Evet/12 ay üzerinde"},
        ]

        for i, s in enumerate(sorular):
            soru = Soru(
                anket_id=anket.id,
                metin=s["metin"],
                tip=s["tip"],
                secenekler=s.get("secenekler"),
                sira=i
            )
            db.session.add(soru)
        db.session.commit()
        print("✅ Demografik Bilgiler anketi eklendi.")

    # ÇINLAMA ÖZELLİKLERİ
    if not Anket.query.filter_by(baslik="Çınlama Özellikleri").first():
        anket2 = Anket(baslik="Çınlama Özellikleri")
        db.session.add(anket2)
        db.session.flush()

        sorular2 = [
            {"metin": "Çınlamayı hangi kulağınızda duyuyorsunuz?", "tip": "choice", "secenekler": "Sağ kulak,Sol kulak,Her iki kulak,Baş içinde,Dışarıdan bir ses gibi"},
            {"metin": "Çınlamanın türü nedir?", "tip": "choice", "secenekler": "Uğuldama,Vızıltı,Çınlama,Tıslama,Diğer"},
            {"metin": "Çınlamanın başlangıç zamanı nedir?", "tip": "choice", "secenekler": "1 aydan kısa süre önce,1-3 ay önce,3-6 ay önce,6-12 ay,1-2 sene,2 sene üzeri"},
            {"metin": "Çınlamanızın şiddetinde zamanla değişiklik oldu mu?", "tip": "choice", "secenekler": "Evet/şiddet arttı,Evet/şiddet azaldı,Hayır/aynı kaldı"},
            {"metin": "Çınlamanız sürekli mi yoksa ara sıra mı?", "tip": "choice", "secenekler": "Sürekli,Ara sıra,Zaman zaman kesiliyor"},
            {"metin": "Ailenizde çınlama şikayeti olan bir kişi var mı?", "tip": "choice", "secenekler": "Evet,Hayır"},
            {"metin": "Çınlamanızın başlamasında bildiğiniz bir sebep var mı?", "tip": "choice", "secenekler": "Gürültü,Hastalık,Operasyonlar,Psikoljik travma,Hatırlamıyorum"},
            {"metin": "Çınlamanın sosyal yaşamınıza etkisi nedir?", "tip": "choice", "secenekler": "Hiçbir etkisi yok,Az etkiliyor,Orta derecede etkiliyor,Şiddetli etkiliyor,Çok şiddetli etkiliyor"},
            {"metin": "Çınlamanın iş yerindeki performansınıza etkisi nedir?", "tip": "choice", "secenekler": "Hiçbir etkisi yok,Az etkiliyor,Orta derecede etkiliyor,Şiddetli etkiliyor,Çok şiddetli etkiliyor"},
            {"metin": "Çınlamanız psikolojik durumunuzu (depresyon, kaygı) nasıl etkiliyor?", "tip": "choice", "secenekler": "Hiçbir etkisi yok,Az etkiliyor,Orta derecede etkiliyor,Şiddetli etkiliyor,Çok şiddetli etkiliyor"},
        ]

        for i, s in enumerate(sorular2):
            soru = Soru(
                anket_id=anket2.id,
                metin=s["metin"],
                tip=s["tip"],
                secenekler=s.get("secenekler"),
                sira=i
            )
            db.session.add(soru)
        db.session.commit()
        print("✅ Çınlama Özellikleri anketi eklendi.")

    if not Anket.query.filter_by(baslik="Psikoakustik, Hiperakuzi ve Diğer Faktörler").first():
        anket3 = Anket(baslik="Psikoakustik, Hiperakuzi ve Diğer Faktörler")
        db.session.add(anket3)
        db.session.flush()

        sorular3 = [
            {"metin": "Çınlamanın genel rahatsızlık seviyesini aşağıdaki görsel analog skala ile değerlendirin:", "tip": "choice", "secenekler": "0: Hiç rahatsızlık yok,1–2: Çok hafif rahatsızlık,3–4: Hafif rahatsızlık,5–6: Orta derecede rahatsızlık,7–8: Şiddetli rahatsızlık,9–10: En şiddetli rahatsızlık"},
            {"metin": "Çınlamanın uykuya etkisini aşağıdaki görsel analog skala ile değerlendirin:", "tip": "choice", "secenekler": "0: Hiçbir etkisi yok,1–2: Çok az etkiliyor,3–4: Hafif etkiliyor,5–6: Orta derecede etkiliyor,7–8: Şiddetli etkiliyor,9–10: Çok şiddetli etkiliyor"},
            {"metin": "Çınlamanın konsantrasyona etkisini aşağıdaki görsel analog skala ile değerlendirin:", "tip": "choice", "secenekler": "0: Hiçbir etkisi yok,1–2: Çok az etkiliyor,3–4: Hafif etkiliyor,5–6: Orta derecede etkiliyor,7–8: Şiddetli etkiliyor,9–10: Çok şiddetli etkiliyor"},
            {"metin": "Çınlamanın işitmeye etkisini aşağıdaki görsel analog skala ile değerlendirin:", "tip": "choice", "secenekler": "0: Hiçbir etkisi yok,1–2: Çok az etkiliyor,3–4: Hafif etkiliyor,5–6: Orta derecede etkiliyor,7–8: Şiddetli etkiliyor,9–10: Çok şiddetli etkiliyor"},
            {"metin": "Seslere karşı hassasiyetiniz var mı?", "tip": "choice", "secenekler": "Evet/bazı seslere karşı aşırı hassasım,Hayır/seslere karşı duyarlılığım normal"},
            {"metin": "Çınlama şiddeti, seslere karşı duyarlılığınızla ilişkilendirilebilir mi?", "tip": "choice", "secenekler": "Evet/çınlama daha şiddetli olduğunda seslere karşı duyarlılığım artıyor,Hayır/çınlama ile seslere karşı duyarlılığım arasında bir ilişki yok"},
            {"metin": "Günlük yaşamda duyduğunuz bazı sesler sizi rahatsız ediyor mu?", "tip": "choice", "secenekler": "Evet/bazı sesler oldukça rahatsız edici,Hayır/duyduğum sesler normal seviyelerde ve rahatsız etmiyor"},
            {"metin": "Çınlama ile ilgili olarak daha önce herhangi bir terapi/tedavi aldınız mı?", "tip": "choice", "secenekler": "Hayır,Evet"},
            {"metin": "Eğer aldıysanız aldığınız terapi ve tedavileri aşağıdan seçiniz.", "tip": "multi_choice", "secenekler": "İlaç,Manuel Terapi,Psikoterapi,Ses terapisi (işitme cihazlı ya da cihazsız),Alternatif tıp,rTMS, TENS,İşitme cihazı"},
            {"metin": "Aşağıdaki hareket veya dokunuşlardan herhangi biri çınlamanızın şiddetini etkiliyor mu? (Birden fazla seçenek işaretleyebilirsiniz)", "tip": "multi_choice", "secenekler": "Boyun çevirme (sağ/sol),Baş öne/arkaya eğme,Çeneyi sıkma,Omuz kaslarını kasma,Gözleri sıkıca kapama,Boyun/çene bölgesine baskı uygulama,Yüz/kulak bölgesine dokunma,Egzersiz sonrası"},
            {"metin": "Çınlamanızın artmasına neden olduğunu düşündüğünüz durumlar nelerdir? (Birden fazla seçenek işaretleyebilirsiniz)", "tip": "multi_choice", "secenekler": "Stres,Yorgunluk,Sessizlik,Gürültülü ortamlar,Uyku eksikliği,Kafeinli içecekler,Alkol tüketimi,Sigara kullanımı,Tuzlu gıdalar,Şekerli gıdalar,Fiziksel egzersiz,Konsantrasyon gerektiren işler,Bilgisayar/telefon kullanımı,Belirgin bir artış fark etmiyorum,Diğer"},
            {"metin": "Çınlamanızın azalmasına neden olduğunu düşündüğünüz durumlar nelerdir? (Birden fazla seçenek işaretleyebilirsiniz)", "tip": "multi_choice", "secenekler": "Dikkatimi dağıtacak bir işle meşgul olmak,Hafif arka plan sesleri (örneğin müzik/TV/ doğa sesleri),Meditasyon / nefes egzersizleri,Fiziksel aktivite / spor,Uyumak,Duş / akan su sesi,Masaj, gevşeme teknikleri,Doğada vakit geçirmek,Sosyal aktivite / arkadaşlarla vakit,İlaç / terapi sonrası,Belirgin bir azalma fark etmiyorum,Diğer"},
            {"metin": "Çınlama tedavisinde size önerilen bir ilaç var mı? (Birden fazla seçenek işaretleyebilirsiniz)", "tip": "multi_choice", "secenekler": "Betaserc,Vasoserc,Ginkobiloba,Sefal,Dramamine,Vitamin,Diğer"},
        ]

        for i, s in enumerate(sorular3):
            soru = Soru(
                anket_id=anket3.id,
                metin=s["metin"],
                tip=s["tip"],
                secenekler=s.get("secenekler"),
                sira=i
            )
            db.session.add(soru)

        db.session.commit()
        print("✅ Psikoakustik, Hiperakuzi ve Diğer Faktörler anketi eklendi.")
    if not Anket.query.filter_by(baslik="Anksiyete ve Depresyon Ölçeği").first():
        anket4 = Anket(baslik="Anksiyete ve Depresyon Ölçeği")
        db.session.add(anket4)
        db.session.flush()

        sorular4 = [
            {"metin": "Kendimi gergin 'patlayacak gibi' hissediyorum.", "tip": "choice", "secenekler": "Hiçbir zaman,Zaman zaman/bazen,Birçok zaman,Çoğu zaman"},
            {"metin": "Eskiden zevk aldığım şeylerden hala zevk alıyorum.", "tip": "choice", "secenekler": "Aynı eskisi kadar,Pek eskisi kadar değil,Yalnızca biraz eskisi kadar,Hiçbir zaman"},
            {"metin": "Sanki kötü bir şey olacakmış gibi bir korkuya kapılıyorum.", "tip": "choice", "secenekler": "Hayır/ hiç öyle değil,Biraz/ ama beni pek endişelendirmiyor,Evet/ama çok da şiddetli değil,Kesinlikle öyle ve oldukça da şiddetli"},
            {"metin": "Gülebiliyorum ve olayların komik tarafını görebiliyorum.", "tip": "choice", "secenekler": "Her zaman olduğu kadar,Şimdi pek o kadar değil,Şimdi kesinlikle o kadar değil,Artık hiç değil"},
            {"metin": "Aklımdan endişe verici düşünceler geçiyor.", "tip": "choice", "secenekler": "Çoğu zaman,Birçok zaman,Zaman zaman/çok sık değil,Yalnızca bazen"},
            {"metin": "Kendimi neşeli hissediyorum.", "tip": "choice", "secenekler": "Hiçbir zaman,Sık değil,Bazen,Çoğu zaman"},
            {"metin": "Rahat rahat oturabiliyorum ve kendimi gevşek hissediyorum.", "tip": "choice", "secenekler": "Kesinlikle,Genellikle,Sık değil,Hiçbir zaman"},
            {"metin": "Kendimi sanki durgunlaşmış gibi hissediyorum.", "tip": "choice", "secenekler": "Hemen hemen her zaman,Çok sık,Bazen,Hiçbir zaman"},
            {"metin": "Sanki içim pır pır ediyormuş gibi bir tedirginliğe kapılıyorum.", "tip": "choice", "secenekler": "Hiçbir zaman,Bazen,Oldukça sık,Çok sık"},
            {"metin": "Dış görünüşüme ilgimi kaybettim.", "tip": "choice", "secenekler": "Kesinlikle,Gerektiği kadar özen göstermiyorum,Pek o kadar özen göstermeyebilirim,Her zamanki kadar özen gösteriyorum"},
            {"metin": "Kendimi sanki hep bir şey yapmak zorundaymışım gibi huzursuz hissediyorum.", "tip": "choice", "secenekler": "Gerçekten de çok fazla,Oldukça fazla,Çok fazla değil,Hiç değil"},
            {"metin": "Olacakları zevkle bekliyorum.", "tip": "choice", "secenekler": "Her zaman olduğu kadar,Her zamankinden biraz daha az,Her zamankinden kesinlikle daha az,Hemen hemen hiç"},
            {"metin": "Aniden panik duygusuna kapılıyorum.", "tip": "choice", "secenekler": "Gerçekten de çok sık,Oldukça sık,Çok sık değil,Hiçbir zaman"},
            {"metin": "İyi bir kitap, televizyon ya da radyo programından zevk alabiliyorum.", "tip": "choice", "secenekler": "Sıklıkla,Bazen,Pek sık değil,Çok seyrek"},
        ]

        for i, s in enumerate(sorular4):
            soru = Soru(
                anket_id=anket4.id,
                metin=s["metin"],
                tip=s["tip"],
                secenekler=s.get("secenekler"),
                sira=i
            )
            db.session.add(soru)

        db.session.commit()
        print("✅ Anksiyete ve Depresyon Ölçeği anketi başarıyla eklendi.")

    if not Anket.query.filter_by(baslik="Tinnitus Handicap Inventory (THI)").first():
        anket5 = Anket(baslik="Tinnitus Handicap Inventory (THI)")
        db.session.add(anket5)
        db.session.flush()

        thi_sorular = [
            "Çınlamanız nedeniyle dikkatinizi toplamada güçlük çekiyor musunuz?",
            "Çınlama sesinin yüksekliği nedeniyle insanları duymada güçlük çekiyor musunuz?",
            "Çınlamanız sizi sinirlendiriyor mu?",
            "Çınlamanız kafanızın karışması hissi uyandırıyor mu?",
            "Çınlamanız nedeniyle umutsuzluk hissediyor musunuz?",
            "Çınlamanızdan büyük oranda şikayetçi misiniz?",
            "Çınlamanız nedeniyle gece uykuya dalmakta güçlük çekiyor musunuz?",
            "Çınlamanızdan kurtulamayacağınız hissine kapılıyor musunuz?",
            "Çınlamanız sosyal aktivitelerden keyif almanızı engelliyor mu?",
            "Çınlamanız nedeniyle kendiniz engellenmiş hissediyor musunuz?",
            "Çınlamanız nedeniyle felaket bir hastalığa yakalanmış hissine kapılıyor musunuz?",
            "Çınlamanız hayattan zevk almanızı güçleştiriyor mu?",
            "Çınlamanız işinize veya evinizle ilgili sorumluluklarınızı yerine getirmenizi engelliyor mu?",
            "Çınlamanız nedeniyle kendinizi sıklıkla alıngan bulduğunuz oluyor mu?",
            "Çınlamanız nedeniyle sizin için okumak güç oluyor mu?",
            "Çınlamanız sizi üzüyor mu?",
            "Çınlama probleminiz ailenizdeki bireylerle ve arkadaşlarınızla olan ilişkilerinizde baskıya yol açtığını hissediyor musunuz?",
            "Dikkatinizi, kulak çınlamasından uzaklaştırıp diğer şeylere odaklamayı güç buluyor musunuz?",
            "Çınlamanız üzerinde hiçbir kontrolünüzün olmadığını hissediyor musunuz?",
            "Çınlamanız nedeniyle sık sık kendinizi yorgun hissediyor musunuz?",
            "Çınlamanız nedeniyle kendinizi çökmüş hissediyor musunuz?",
            "Çınlamanız sizi sinirli hissettiriyor mu?",
            "Çınlamanızla artık başa çıkamadığınızı düşünüyor musunuz?",
            "Çınlamanız sıkıntılıyken daha kötü oluyor mu?",
            "Çınlamanız sizde güvensizlik hissi uyandırıyor mu?"
        ]

        for i, soru_metni in enumerate(thi_sorular):
            soru = Soru(
                anket_id=anket5.id,
                metin=soru_metni,
                tip="choice",
                secenekler="Evet,Hayır,Bazen",
                sira=i
            )
            db.session.add(soru)

        db.session.commit()
        print("✅ Tinnitus Handicap Inventory (THI) anketi eklendi.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Varsayılan admin ekleniyor
        if not User.query.filter_by(email="admin@example.com").first():
            admin = User(name="Admin", email="admin@example.com", password="1234", role="admin")
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin kullanıcısı eklendi: admin@example.com / 1234")

        # 👇 BURASI ÖNEMLİ: Artık app context içindeyiz
        create_default_surveys()

    app.run(debug=True)



