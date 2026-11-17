# Data Dictionary: India-Specific POI Conflation

**Dataset Scope:** Bengaluru Metropolitan Area (Bruhat Bengaluru Mahanagara Palike — BBMP)  
**Spatial Reference System:** WGS 84 (EPSG:4326) / UTM Zone 43N (EPSG:32643)  
**Target Milestone:** Milestone 2 (Data Ingestion & Canonical Harmonization)  

---

## 1. Architectural Data Layers Overview

The data ingestion foundation maintains a strict separation between raw extracted provider data and the transformed canonical representations:

```
+-------------------------------------------------------------+
|                      SOURCE PROVIDERS                       |
|   Overture Maps Foundation (S3)       OpenStreetMap (PBF)   |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     RAW STORAGE LAYER                       |
|   data/raw/overture/bengaluru_overture_places.parquet       |
|   data/raw/osm/bengaluru_osm_pois.parquet                   |
|   (Strictly preservationist: source-native schemas/tags)    |
+------------------------------+------------------------------+
                               |
                 Canonical Harmonization Layer
                               |
                               v
+-------------------------------------------------------------+
|                  PROCESSED CANONICAL LAYER                  |
|   data/processed/canonical_pois.parquet                     |
|   (Harmonized POI schema: typed, normalized, validated)     |
+-------------------------------------------------------------+
```

---

## 2. Processed Layer: Canonical POI Schema

**Target Artifact:** `data/processed/canonical_pois.parquet`  
**Storage Format:** Apache Parquet (Zstandard compression)  
**Schema Definition:** Explicit PyArrow Schema (`get_canonical_arrow_schema()`)

| Field Name | Data Type | Nullable | Description & Domain | Sample Value |
| :--- | :--- | :--- | :--- | :--- |
| `poi_source` | `VARCHAR` | No | Originating source dataset identifier: `OVERTURE` or `OSM`. | `"OVERTURE"` |
| `source_record_id` | `VARCHAR` | No | Unique identifier from the upstream provider. For Overture, standard UUID; for OSM, `{type}/{id}`. | `"node/12345678"`, `"6df811c4-29a2..."` |
| `source_release` | `VARCHAR` | No | Upstream release snapshot or extraction date. | `"2026-10-21.0"`, `"geofabrik-2026-11-17"` |
| `name_original` | `VARCHAR` | No | Primary name as recorded in source data. Preserves original casing, script, and punctuation. | `"M/s Sri Lakshmi Provision Store"` |
| `name_normalized` | `VARCHAR` | No | Cleaned name: lowercased, non-alphanumeric punctuation removed, whitespace collapsed. | `"m s sri lakshmi provision store"` |
| `alternate_names` | `LIST[VARCHAR]` | No | List of alternative names, common names, translations, or previous aliases. Empty list if none. | `["Lakshmi General Store", "ಲಕ್ಷ್ಮಿ ಸ್ಟೋರ್ಸ್"]` |
| `name_en` | `VARCHAR` | Yes | Explicit English name where tagged separately. | `"Sri Lakshmi Store"` |
| `name_kn` | `VARCHAR` | Yes | Explicit Kannada script representation (`name:kn` in OSM, or extracted from Overture name rules). | `"ಶ್ರೀ ಲಕ್ಷ್ಮಿ ಪ್ರೊವಿಷನ್ ಸ್ಟೋರ್"` |
| `latitude` | `DOUBLE` | No | WGS 84 latitude in decimal degrees. Must lie within BBMP bounds ($12.833^\circ$ to $13.143^\circ$). | `12.975012` |
| `longitude` | `DOUBLE` | No | WGS 84 longitude in decimal degrees. Must lie within BBMP bounds ($77.459^\circ$ to $77.784^\circ$). | `77.601245` |
| `geometry_wkt` | `VARCHAR` | No | Well-Known Text geometry representation (`POINT (lon lat)`). | `"POINT (77.601245 12.975012)"` |
| `category_original` | `VARCHAR` | No | Raw source classification string (e.g., `amenity=cafe`, `taxonomy:indian_restaurant`). | `"amenity=restaurant"`, `"shopping"` |
| `category_normalized`| `VARCHAR` | No | Standardized high-level canonical taxonomy (see Section 4). | `"sustenance"` |
| `address_original` | `VARCHAR` | Yes | Raw freeform address text if provided by upstream source. | `"12, 100 Feet Rd, Indiranagar"` |
| `address_locality` | `VARCHAR` | Yes | Neighborhood, suburb, ward, or postal locality. | `"Indiranagar"`, `"Koramangala"` |
| `address_postcode` | `VARCHAR` | Yes | 6-digit Indian Postal Index Number (PIN Code), validated to Karnataka regex `^560\d{3}$`. | `"560038"` |
| `phone` | `VARCHAR` | Yes | Contact telephone number formatted as string. | `"+91 80 2520 1234"` |
| `website` | `VARCHAR` | Yes | Verified website or official social URL. | `"https://example.com"` |
| `confidence` | `DOUBLE` | Yes | Source confidence rating ($0.0 \le c \le 1.0$). Provided by Overture; defaults to $1.0$ for OSM. | `0.89` |
| `source_timestamp` | `VARCHAR` | Yes | Timestamp of source changeset / record update (ISO 8601). | `"2026-08-15T10:30:00Z"` |
| `ingestion_timestamp`| `VARCHAR`| No | UTC timestamp when record was parsed into the canonical model. | `"2026-11-17T08:34:19Z"` |
| `provenance_metadata`| `VARCHAR`| No | JSON-encoded dictionary capturing upstream provider metadata (changeset, version, providers). | `'{"upstream_sources": ["Meta", "Bing"]}'` |

---

## 3. Raw Storage Layer Schemas

### 3.1 Raw Overture Places Schema
**Artifact:** `data/raw/overture/bengaluru_overture_places.parquet`

- `id` (`VARCHAR`): Primary Overture UUID.
- `name_primary` (`VARCHAR`): Primary entity name string.
- `names_rules` (`LIST[STRUCT]`): Multilingual variants, perspective metadata, script codes.
- `basic_category` (`VARCHAR`): Legacy / high-level category string.
- `taxonomy_primary` (`VARCHAR`): Hierarchical taxonomy category identifier.
- `taxonomy_alternates` (`LIST[VARCHAR]`): Additional taxonomic classifications.
- `confidence` (`DOUBLE`): Probabilistic confidence score assigned by Overture ingestion models.
- `addresses` (`LIST[STRUCT]`): Structured address array (freeform, locality, postcode, region, country).
- `addr_freeform` (`VARCHAR`): Extracted primary freeform street address.
- `addr_locality` (`VARCHAR`): Extracted city / suburb name.
- `addr_postcode` (`VARCHAR`): Extracted postal PIN code.
- `sources` (`LIST[STRUCT]`): Upstream data source attribution array (Meta, Microsoft, Foursquare, etc.).
- `operating_status` (`VARCHAR`): Operational flag (`operational`, `temporarily_closed`, `permanently_closed`).
- `version` (`INT32`): Overture entity version number.
- `longitude` (`DOUBLE`): X coordinate (WGS 84).
- `latitude` (`DOUBLE`): Y coordinate (WGS 84).
- `geometry_wkt` (`VARCHAR`): Point WKT representation.

### 3.2 Raw OpenStreetMap POI Schema
**Artifact:** `data/raw/osm/bengaluru_osm_pois.parquet`

- `osm_type` (`VARCHAR`): Element type: `node` or `way`.
- `osm_id` (`VARCHAR`): Prefixed identifier (`node/12345` or `way/67890`).
- `numeric_id` (`INT64`): Native 64-bit OSM integer ID.
- `version` (`INT32`): OSM feature version number.
- `timestamp` (`VARCHAR`): ISO 8601 timestamp of last changeset commit.
- `latitude` (`DOUBLE`): Node latitude or way centroid latitude.
- `longitude` (`DOUBLE`): Node longitude or way centroid longitude.
- `geometry_wkt` (`VARCHAR`): Point WKT representation.
- `name` (`VARCHAR`): Default `name` tag.
- `name_en` (`VARCHAR`): Explicit `name:en` tag.
- `name_kn` (`VARCHAR`): Explicit `name:kn` Kannada script tag.
- `name_hi` (`VARCHAR`): Explicit `name:hi` Hindi script tag.
- `category_original` (`VARCHAR`): Primary key=value tag (e.g., `amenity=cafe`).
- `matched_keys` (`LIST[VARCHAR]`): All POI keys present on the element.
- `addr_freeform` (`VARCHAR`): Concatenated housenumber and street tags.
- `addr_locality` (`VARCHAR`): `addr:city` or `addr:suburb` tags.
- `addr_postcode` (`VARCHAR`): `addr:postcode` tag.
- `phone` (`VARCHAR`): `phone` or `contact:phone` tag.
- `website` (`VARCHAR`): `website` or `contact:website` tag.
- `raw_tags_json` (`VARCHAR`): Complete JSON serialization of all element tags.

---

## 4. Canonical Category Taxonomy

All POIs are mapped from source-specific tags to one of ten mutually exclusive canonical categories:

| Category Code | Description | Example OSM Tags | Example Overture Taxonomies |
| :--- | :--- | :--- | :--- |
| `sustenance` | Food and beverage consumption | `amenity=restaurant`, `amenity=cafe`, `amenity=fast_food` | `restaurant`, `indian_restaurant`, `cafe`, `bakery` |
| `retail` | Commercial retail, markets, goods | `shop=supermarket`, `shop=convenience`, `shop=clothes` | `shopping`, `clothing_store`, `supermarket`, `department_store`|
| `healthcare` | Medical and pharmaceutical services | `amenity=hospital`, `amenity=pharmacy`, `healthcare=*` | `hospital`, `medical_center`, `pharmacy`, `clinic` |
| `hospitality` | Temporary accommodation and lodging | `tourism=hotel`, `tourism=guest_house`, `tourism=hostel` | `hotel`, `motel`, `resort`, `bed_and_breakfast` |
| `financial` | Banking, ATMs, monetary services | `amenity=bank`, `amenity=atm` | `bank`, `atm`, `financial_service` |
| `education` | Academic institutions, libraries | `amenity=school`, `amenity=college`, `amenity=university` | `school`, `college_or_university`, `educational_institution` |
| `commercial_services`| Corporate offices, professional services| `office=company`, `office=it`, `craft=*` | `professional_service`, `real_estate_service`, `corporate_office`|
| `civic_religious`| Places of worship, municipal services | `amenity=place_of_worship`, `amenity=police`, `amenity=post_office`| `place_of_worship`, `temple`, `church`, `government_office` |
| `leisure_tourism`| Parks, heritage, culture, athletics | `leisure=park`, `tourism=museum`, `historic=monument` | `park`, `tourist_attraction`, `museum`, `movie_theater` |
| `other` | Unmapped or general point features | All unclassified tags | Miscellaneous classifications |
