# Ingestion & Normalization Pipeline

This package contains Python-based data ingestion clients, normalization scripts, and the reference aggregation engine.

## Directory Structure

* `src/ingestors/`: API clients for DIP (Bundestag), Bundestag XML, abgeordnetenwatch.de, and dawum.de.
* `src/aggregation.py`: Reference implementation of the weighted similarity and confidence aggregation formulas.
* `evidence_config/`: Directory for per-legislature YAML configuration files.
* `tests/`: Integration and unit tests for the pipeline.
