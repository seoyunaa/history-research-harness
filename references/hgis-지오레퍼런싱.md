# 지오레퍼런싱 워크플로 — 고지도·영인본을 좌표계에 정합

하네스의 지리 재현성(좌표 화이트리스트·도표 매니페스트)에 더하는 층 = **래스터(스캔 지도)의 좌표 정합**. {예: 고지도 영인본, 근대 지도첩, 도서관이 공개한 스캔 지도}를 QGIS 도표 위에 얹으려면 이 절차를 거친다.

## 표준 절차 (파일이 진실 — GUI 클릭이 아니라)

1. **대응점(GCP) 수집** — 스캔 이미지의 픽셀 위치 ↔ 실좌표. 실좌표는 반드시 전거에 정박(게이지티어 id·고증 면수·마스터 gm_id). GCP CSV 양식: `pixel_x,pixel_y,lon,lat,source,certainty[,note]` — **source 공란은 도구가 거부**한다(출처 없는 좌표 금지).
2. **정합 실행**:
   ```
   python tools/georef.py <스캔.png> <gcp.csv> <출력.tif> [--method tps]
   ```
   QGIS 번들 GDAL(gdal_translate -gcp → gdalwarp)로 headless 실행. `--method tps`(Thin Plate Spline)는 비선형 왜곡(고지도)에 적합 — GCP 10점 이상 권장. 산출 = GeoTIFF + 매니페스트(재현 명령·입력 SHA-256·GCP 전문·gdalinfo 검증).
3. **도표 결합**: 산출 GeoTIFF를 QGIS 레이어로 얹어 내보내거나, rioxarray/rasterio(파이썬)로 도표에 오버레이한다. 래스터 파이썬 처리에 쓰는 rasterio·rioxarray는 기본 환경(`environment.yml`)에 없으므로 필요할 때 따로 설치한다. 어느 방식이든 도표 매니페스트(`corpus/_figure-manifest-template.md`)에 입력·명령·라이선스를 남긴다.

## 주의

- **회화식 고지도**는 측량 지도가 아니다. 정합 잔차가 크면 위치 측정 근거로 쓰지 말고 오버레이(시각 참고) 전용으로 매니페스트에 명기한다.
- 스캔 이미지의 **이용 조건**(소장 기관의 재배포·게재 허락)을 확인하고 매니페스트에 적는다.
- 정합 결과는 AI·도구가 만든 파생물이다. GCP의 전거와 잔차를 저자가 검토하기 전까지 논문 도판의 근거로 쓰지 않는다.

## GCP 개념 학습 (입문용)

- Programming Historian, **"Georeferencing in QGIS"** — 컨트롤 포인트·러버시팅 개념(UI는 낡았을 수 있으나 개념은 유효): https://programminghistorian.org/en/lessons/georeferencing-qgis
- Programming Historian의 "Introduction to Map Warper"(브라우저 정합)와 "Geocoding Historical Data using QGIS"(지명표→좌표 — 게이지티어 워크플로 접점)
- **Allmaps**: IIIF 스캔이 있는 지도는 Allmaps 편집기에서 GCP를 찍어 Georeference Annotation(JSON)을 만들고 QGIS XYZ 레이어로 쓸 수 있다. 도서관 IIIF 소장 고지도에 적합: https://allmaps.org
- 래스터 파이썬 커리큘럼: Carpentries Incubator "Geospatial Raster and Vector Data with Python"(rioxarray)

## 경계·판도 데이터

`references/connectors.md` §경계·판도 데이터 — 역사 행정경계·정치체 판도·현대 베이스맵 후보와 라이선스 주의(재배포 금지 데이터는 로컬 캐시만, 현대 하도·해안선은 사료 시대와 다르다).
