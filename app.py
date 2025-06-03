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

    anketler = Survey.query.filter_by(hasta_id=hasta_id).order_by(Survey.tarih.desc()).all()
    hasta = User.query.get(hasta_id)

    anket_sonuclari = []
    for a in anketler:
        anket_adi = Anket.query.get(a.anket_id).baslik
        cevap_dict = json.loads(a.cevaplar)
        sorular = Soru.query.filter_by(anket_id=a.anket_id).all()
        soru_cevaplar = []
        for soru in sorular:
            cevap = cevap_dict.get(str(soru.id), "(boş)")
            if isinstance(cevap, list):
                cevap = ', '.join(cevap)
            soru_cevaplar.append({'soru': soru.metin, 'cevap': cevap})
        anket_sonuclari.append({
            'anket_adi': anket_adi,
            'tarih': a.tarih,
            'sorular': soru_cevaplar
        })

    return render_template('hasta_anketleri.html', hasta=hasta, anketler=anket_sonuclari)

@app.route('/hasta')
@login_required
def hasta_panel():
    if current_user.role != 'hasta':
        return redirect('/')
    anketler = Anket.query.all()
    yapilan_anketler = Survey.query.filter_by(hasta_id=current_user.id).order_by(Survey.tarih.desc()).all()
    gecmis = []
    for survey in yapilan_anketler:
        anket = Anket.query.get(survey.anket_id)
        cevaplar = json.loads(survey.cevaplar)
        sorular = Soru.query.filter_by(anket_id=anket.id).all()
        soru_cevaplar = []
        for soru in sorular:
            cevap = cevaplar.get(str(soru.id), '')
            if isinstance(cevap, list):
                cevap = ', '.join(cevap)
            soru_cevaplar.append({'soru': soru.metin, 'cevap': cevap})
        gecmis.append({
            'anket_adi': anket.baslik,
            'tarih': survey.tarih,
            'icerik': soru_cevaplar
        })
    return render_template('hasta_panel.html', user=current_user, anketler=anketler, gecmis_anketler=gecmis)

@app.route('/anket_doldur/<int:anket_id>', methods=['GET', 'POST'])
@login_required
def anket_doldur(anket_id):
    if current_user.role != 'hasta':
        return redirect('/')
    anket = Anket.query.get_or_404(anket_id)
    sorular = anket.sorular
    if request.method == 'POST':
        cevaplar = {}
        for soru in sorular:
            if soru.tip == "multi_choice":
                secimler = request.form.getlist(f"soru_{soru.id}_checkbox")
                cevaplar[str(soru.id)] = secimler
            else:
                cevaplar[str(soru.id)] = request.form.get(f"soru_{soru.id}")
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

# UYGULAMA BAŞLAT
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email="admin@example.com").first():
            admin = User(name="Admin", email="admin@example.com", password="1234", role="admin")
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin kullanıcısı eklendi: admin@example.com / 1234")
    app.run(debug=True)
