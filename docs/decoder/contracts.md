# Decoder contracts

The following are current behavioral contracts:

- Input is validated SigMF metadata/data, including datatype, sample rate,
  interval, orientation, and file-coordinate identity.
- Output is deterministic and includes a schema-versioned manifest with input
  identity, configuration, coordinates, health, timing, resource, and stage
  information.
- MFSK32 and MFSK64 text decode follows the wire behavior in
  [`mfsk_wire_spec.md`](mfsk_wire_spec.md).
- MFSK64 grayscale and color picture assembly preserves the specified geometry,
  component order, and completion behavior.
- Text, picture, and mode transitions must not silently discard valid content.
- Invalid, incomplete, or uncertain material is represented explicitly rather
  than reported as successful empty output.
- Atomic publication and stable artifact identities are required for durable
  corpus evidence and appliance ingestion.

The machine-readable vectors and fixture evidence at the repository-level
`docs/` paths are part of the compatibility evidence. Changes to them require
independent review and test updates.
