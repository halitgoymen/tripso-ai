# Tripso AI

AI destekli seyahat planlama servisi. Foursquare (mekan verisi) ve Travelpayouts (uçuş
arama) API'lerini yerel Qwen modeliyle (Ollama) birleştirip kişiselleştirilmiş seyahat
planları ve mekan önerileri üretir.

## Özellikler

- `/api/plan` — Foursquare mekan verisi + Qwen ile seyahat planı üretimi
- `/api/flights` — Travelpayouts uçuş arama + Qwen analizi
- Basit web dashboard (`tripso_web.html`)
- CLI arayüzü (`tripso_cli.py`)

## Teknoloji

- Python (stdlib `http.server`, ek framework yok)
- Ollama (yerel Qwen modeli)
- Foursquare Places API, Travelpayouts API

## Kurulum

`.env` dosyasına şunları ekle (repo'ya commitlenmez):

```
GEOAPIFY_KEY=
TRAVELPAYOUTS_TOKEN=
OLLAMA_URL=
OLLAMA_MODEL=
SERVER_PORT=8080
```

## Çalıştırma

```
python tripso_server.py
```

Dashboard: http://localhost:8080
