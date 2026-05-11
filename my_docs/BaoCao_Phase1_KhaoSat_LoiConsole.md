# Bao cao Phase 1 - Khao sat loi Console Dashboard

Ngay ghi nhan: 2026-05-11
Pham vi: loi console trong `my_docs/Test_QC.md`, trang `http://localhost:8080/dashboard?zone=A01`, backend `http://localhost:8000`.

## 1. Ket luan nhanh

Lan upgrade nay van chi dat khoang 10% so voi ky vong vi flow realtime/imagery chua on dinh o moi truong chay that. Hai nhom loi chinh dang chan trai nghiem dashboard:

1. WebSocket `ws://localhost:8000/ws/updates` ket noi that bai lap lai.
2. Anh preview imagery `http://localhost:8000/v1/imagery/preview/...` bi browser chan do khong co header CORS `Access-Control-Allow-Origin`.

Cac loi nay lam dashboard mat cap nhat realtime, map overlay/preview anh ve tinh khong load duoc, va console bi spam reconnect nen kho danh gia cac tinh nang khac.

## 2. Bang chung tu console

Trich loi nguoi dung ghi nhan trong `my_docs/Test_QC.md`:

```text
WebSocket connection to 'ws://localhost:8000/ws/updates' failed
Access to fetch at 'http://localhost:8000/v1/imagery/preview/S2C_48PVS_20260414_0_L2A?mode=rgb' from origin 'http://localhost:8080' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
AJAXError: Failed to fetch (0): http://localhost:8000/v1/imagery/preview/S2C_48PVS_20260414_0_L2A?mode=rgb
```

## 3. Cac file lien quan da khao sat

- `backend/api_gateway/main.py`: co cau hinh `CORSMiddleware`, allow origins lay tu `settings.CORS_ORIGINS`; route imagery gan dependencies doc quyen admin read.
- `backend/core/config.py`: `CORS_ORIGINS` doc tu bien moi truong, mac dinh chi co `http://localhost:3000` neu khong load `.env`.
- `.env`: da khai bao `CORS_ORIGINS=http://localhost:3000,http://localhost:8080`, `VITE_API_BASE_URL=http://localhost:8000`, `VITE_WS_URL=ws://localhost:8000/ws/updates`, `AUTH_REQUIRED=false`, `WS_REQUIRE_AUTH=false`.
- `backend/features/websocket/router.py`: route `/ws/updates`, tu choi neu origin khong nam trong `CORS_ORIGINS`, sau do moi `accept()`.
- `backend/features/websocket/auth.py`: `is_allowed_ws_origin()` bat buoc request phai co `Origin` va Origin phai khop `settings.CORS_ORIGINS`.
- `backend/features/imagery/router.py`: route `/v1/imagery/preview/{scene_id}` tra `StreamingResponse` image/png.
- `frontend/src/lib/api/client.ts`: frontend goi API mac dinh `http://localhost:8000`, WS mac dinh `ws://localhost:8000/ws/updates`.
- `frontend/src/lib/api/index.ts`: `toAbsoluteApiUrl()` bien path preview thanh URL tuyet doi backend, nen browser thuc hien cross-origin fetch/image tu `8080` sang `8000`.
- `frontend/src/lib/realtime/useWebSocket.ts`: khi WS loi se dong socket va reconnect exponential backoff, gay spam console neu backend lien tuc tu choi.
- `frontend/src/components/dashboard/ZoneMap.tsx`: MapLibre dung imagery overlay URL; khi fetch anh bi CORS se bao `AJAXError: Failed to fetch (0)`.

## 4. Phan tich nguyen nhan kha nang cao

### 4.1 CORS khong duoc gan vao response preview

Backend da co `CORSMiddleware` tai `backend/api_gateway/main.py`, nhung console noi response preview khong co `Access-Control-Allow-Origin`. Kha nang cao nhat:

- Process backend dang chay khong load dung file `.env`, nen `CORS_ORIGINS` fallback ve `http://localhost:3000`, khong co `http://localhost:8080`.
- Hoac request preview dang di vao mot process/port/proxy khac khong phai app `backend/api_gateway/main.py` hien tai.
- Hoac exception/response bi middleware/proxy khac cat header truoc khi toi browser.

Dau hieu quan trong: `.env` dung da co `http://localhost:8080`, nen neu backend load dung `.env` thi response tu FastAPI CORSMiddleware phai co CORS header cho origin nay.

### 4.2 Preview imagery co the dang tra loi loi truoc khi render anh

Route preview goi `get_scene_for_preview(scene_id)`. Ham nay load scene tu persistence, neu loi hoac khong thay scene se tra `None`, route nem `AgTechError` 404 `Scene not found`.

Scene loi trong console la `S2C_48PVS_20260414_0_L2A`; can kiem tra scene nay co ton tai trong database/cache `zone_imagery` khong. Neu khong ton tai, backend co the tra 404, nhung browser lai hien CORS truoc nen frontend khong doc duoc noi dung loi.

### 4.3 WebSocket bi tu choi truoc khi accept

`/ws/updates` co cac dieu kien chan truoc `websocket.accept()`:

- Origin phai ton tai va nam trong `settings.CORS_ORIGINS`.
- Neu `WS_REQUIRE_AUTH=true`, phai co bearer token hop le.
- Rate limit handshake co the tu choi neu reconnect lap lai.

Trong `.env`, `WS_REQUIRE_AUTH=false`, nen auth khong phai nguyen nhan neu `.env` duoc load dung. Neu backend khong load `.env`, mac dinh `WS_REQUIRE_AUTH=true` va `CORS_ORIGINS` chi co `http://localhost:3000`; luc do frontend `localhost:8080` se bi dong socket ngay, dung voi hien tuong console spam.

### 4.4 Frontend fallback chua bao phu anh preview/overlay

Cac query imagery co fallback khi API metadata loi (`getZoneImageryLatestSafe`, `getZoneImageryHistorySafe`), nhung khi metadata tra ve URL preview backend hop le ma anh preview bi CORS/404 thi `<img>` va MapLibre overlay van that bai truc tiep. Vi vay UI co the hien co scene nhung anh/overlay khong load duoc.

## 5. Tac dong den muc tieu Phase 1

- Realtime status khong dang tin: WS mat ket noi lien tuc, khong co event invalidation.
- Imagery/Map overlay khong dat nghiem thu: preview RGB/NDVI khong load, MapLibre bao AJAXError.
- UX dashboard bi nhieu loi console, kho demo va kho debug tinh nang model/recommendation.
- Tinh nang co the da code xong mot phan, nhung wiring runtime/env/proxy chua dat, nen muc do hoan thien thuc te chi khoang 10% so voi ky vong.

## 6. De xuat xu ly uu tien

### P0 - Xac minh backend dang load dung config

Can them hoac dung endpoint/debug log de xac nhan runtime settings:

- `APP_ENV` dang la `development`.
- `CORS_ORIGINS` co `http://localhost:8080`.
- `AUTH_REQUIRED=false` trong dev.
- `WS_REQUIRE_AUTH=false` trong dev.
- Port `8000` dung la API Gateway, khong phai service/proxy khac.

Lenh kiem tra goi y:

```powershell
curl.exe -i -H "Origin: http://localhost:8080" "http://localhost:8000/v1/healthz"
curl.exe -i -H "Origin: http://localhost:8080" "http://localhost:8000/v1/imagery/preview/S2C_48PVS_20260414_0_L2A?mode=rgb"
```

Ket qua mong doi phai co:

```text
Access-Control-Allow-Origin: http://localhost:8080
```

### P0 - Sua CORS/WS origin cho moi truong dev

Dam bao process backend load `.env` dung thu muc goc project hoac set bien moi truong truoc khi chay:

```powershell
$env:CORS_ORIGINS="http://localhost:3000,http://localhost:8080"
$env:AUTH_REQUIRED="false"
$env:WS_REQUIRE_AUTH="false"
```

Neu chay qua Docker/compose/VPS, can truyen cac bien nay vao container API Gateway, khong chi nam trong file `.env` local.

### P1 - Kiem tra scene preview ton tai

Can kiem tra `S2C_48PVS_20260414_0_L2A` co trong persistence khong. Neu khong co, can:

- Dong bo metadata latest/history voi scene preview that su co trong DB.
- Hoac route preview tra placeholder image co CORS thay vi nem loi gay blank overlay.
- Hoac frontend bat `onError` cua img/MapLibre image source de fallback sang placeholder local.

### P1 - Giam spam WebSocket reconnect

Frontend nen hien trang thai `offline/reconnecting` nhung khong spam console qua nhieu:

- Tang backoff hoac them max retry trong dev.
- Neu close code `1008` thi dung reconnect lien tuc va hien loi cau hinh/auth.
- Neu `WS_REQUIRE_AUTH=true`, frontend can dua token vao query/header strategy phu hop vi browser WebSocket khong set custom Authorization header bang constructor mac dinh.

### P2 - Bo sung test nghiem thu

Can co test rieng cho runtime wiring:

- API CORS test cho `/v1/imagery/preview/{scene_id}` voi Origin `http://localhost:8080`.
- WS origin test cho `/ws/updates` voi Origin hop le/khong hop le.
- E2E Playwright verify dashboard khong co console error nghiem trong khi load `/dashboard?zone=A01`.

## 7. Tieu chi chap nhan cho lan sua tiep theo

1. Mo `http://localhost:8080/dashboard?zone=A01` khong con CORS error cho preview imagery.
2. WebSocket ket noi thanh cong hoac neu bi tat thi UI hien fallback co chu dich, khong spam console.
3. MapLibre imagery overlay load duoc RGB/NDVI hoac hien placeholder co kiem soat.
4. `curl -i` voi Origin `http://localhost:8080` cho preview co header `Access-Control-Allow-Origin`.
5. E2E dashboard pass va khong ghi nhan `AJAXError: Failed to fetch (0)` cho imagery preview.

## 8. Nhan dinh cuoi

Codebase da co nhieu phan dung huong: CORS middleware, env dev, WS route, imagery preview route, frontend fallback metadata. Tuy nhien loi hien tai cho thay runtime wiring chua dung voi cau hinh dev. Uu tien khong nen tiep tuc them tinh nang moi, ma can khoa chat P0 config/CORS/WS/preview truoc; neu khong, cac lan upgrade tiep theo van se cho cam giac chi dat 10% vi dashboard khong the demo on dinh.
