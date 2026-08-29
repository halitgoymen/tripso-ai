
Nasıl başlatılır:                                                                                                                                                                                       
                                                                                                                                                                                                          
# Terminal 1 — NestJS backend (zaten çalışıyor)                                                                                                                                                         
cd tripso-backend-main && npm run dev                                                                                                                                                                   
                                                                                                                                                                                                          
  # Terminal 2 — Tripso planner server (YENİ)
  python tripso_server.py

  Sonra http://localhost:8080 aç.

  ---
  Ne değişti / eklendi:

  Kayıt akışı: 2 adım — temel bilgiler + seyahat profili (pace, alkol, konaklama, ulaşım, diyet, ilgi alanları, diller) kayıt anında PATCH /users/me/profile'a gönderiliyor.

  Seyahat Planla formu:
  - Plan türü: Tam gün planı (saatli) / Mekan tavsiyesi
  - Uçuş türü: Gidiş-Dönüş / Sadece Gidiş / Sadece Dönüş
  - Kalkış havalimanı: profildeki homeAirportCode'dan otomatik doluyor
  - profileSnapshot: giriş yapılmış kullanıcının profilinden otomatik çekiliyor

  ⚡ Plan & Uçuş Oluştur butonuna basınca:
  1. /api/plan → Foursquare'den mekan çekiyor, Qwen AI plan üretiyor
  2. /api/flights → TravelpayoutsAPI'den uçuş arıyor, Qwen analiz yapıp en iyi uçuşu seçiyor
  3. Her ikisi paralel çalışıyor
  4. Formun altında seyahat planı + uçuş kartları görünüyor (en iyi uçuş ⭐ ile işaretli, Qwen'ın seçme gerekçesi gösteriliyor)