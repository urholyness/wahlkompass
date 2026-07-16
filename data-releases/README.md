# Versioned Data Releases

Public directory containing versioned, signed JSON data bundles representing policy stances, evidence entries, and statement databases.

## Schema Contracts

* `meta.json`: Core release metadata, including release tag, legislature, methodology version, and status flags.
* `statements.json`: The active statement set for the election.
* `parties.json`: Party identities, seat projections, and branding info.
* `positions.json`: Map of derived positions ($p$), confidence scores ($c$), and verification arrays.
* `evidence.json`: Detailed sources, extracts, and coder credits for transparency.
* `exclusions.json`: Pairwise party coalition vetoes with primary reference materials.
