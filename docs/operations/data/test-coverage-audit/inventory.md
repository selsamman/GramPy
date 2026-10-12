# Method-level test inventory

Audit date: 2026-10-11. See [audit](../../test-coverage-audit.md) for rationale, retirement conditions and quality-gate gaps.

248 methods in 42 modules. Observed: {'pass': 242, 'skip': 6}. Proposed dispositions: {'keep': 232, 'consolidate': 4, 'repair': 5, 'rewrite': 1, 'split': 1, 'retire from current product suite': 4, 'reclassify': 1}.

A recommendation is not an implemented deletion. `Self-contained` includes committed oracle data and generated temporary inputs; it does not mean isolated unit code. Elapsed times are one Mac run.

## test_analyze_mfsk_color_fixture.py

known row-plane signal analysis.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [AnalyzeMfskColorFixtureTests.test_locates_known_row_plane_raster](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_analyze_mfsk_color_fixture.py#L19) | pass / 0.7217 | self-contained | keep: Protects known row-plane signal analysis; no full assertion-equivalent replacement established. |

## test_auto_picture_roundtrip.py

public mixed-mode picture integration.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [AutomaticPictureRoundtripTests.test_mixed_picture_modes_keep_order_files_and_resumed_text](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_auto_picture_roundtrip.py#L19) | pass / 11.2475 | self-contained | keep: Protects public mixed-mode picture integration; no full assertion-equivalent replacement established. |

## test_auto_segmented_decode.py

automatic dispatch, ordering and error isolation.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [AutomaticSegmentedDecodeTests.test_auto_dispatches_both_modes_and_publishes_picture](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_auto_segmented_decode.py#L119) | pass / 0.0093 | self-contained | keep: Protects automatic dispatch, ordering and error isolation; no full assertion-equivalent replacement established. |
| [AutomaticSegmentedDecodeTests.test_auto_dispatches_mfsk32_only_picture](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_auto_segmented_decode.py#L210) | pass / 0.0002 | self-contained | keep: Protects automatic dispatch, ordering and error isolation; no full assertion-equivalent replacement established. |
| [AutomaticSegmentedDecodeTests.test_auto_combines_modes_without_losing_order_or_reusing_ids](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_auto_segmented_decode.py#L222) | pass / 0.0004 | self-contained | keep: Protects automatic dispatch, ordering and error isolation; no full assertion-equivalent replacement established. |
| [AutomaticSegmentedDecodeTests.test_failed_mfsk32_picture_does_not_discard_mfsk64_picture](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_auto_segmented_decode.py#L236) | pass / 0.0001 | self-contained | keep: Protects automatic dispatch, ordering and error isolation; no full assertion-equivalent replacement established. |

## test_cli_public_api.py

CLI delegation and output/failure contracts.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [CliPublicApiTests.test_cli_decodes_through_public_api_then_writes_result](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_cli_public_api.py#L16) | pass / 0.0008 | self-contained | keep: Protects CLI delegation and output/failure contracts; no full assertion-equivalent replacement established. |
| [CliPublicApiTests.test_compact_outputs_use_one_product_decode](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_cli_public_api.py#L38) | pass / 0.0007 | self-contained | keep: Protects CLI delegation and output/failure contracts; no full assertion-equivalent replacement established. |
| [CliPublicApiTests.test_diagnostic_alongside_products_still_decodes_once](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_cli_public_api.py#L63) | pass / 0.0005 | self-contained | keep: Protects CLI delegation and output/failure contracts; no full assertion-equivalent replacement established. |
| [CliPublicApiTests.test_compact_terminal_failure_is_published_to_both_paths](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_cli_public_api.py#L81) | pass / 0.0013 | self-contained | keep: Protects CLI delegation and output/failure contracts; no full assertion-equivalent replacement established. |

## test_decode_quality.py

decode-confidence proxy and availability semantics.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [DecodeQualityTests.test_text_margin_invalid_code_and_picture_damage](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_decode_quality.py#L86) | pass / 0.0011 | self-contained | keep: Protects decode-confidence proxy and availability semantics; no full assertion-equivalent replacement established. |
| [DecodeQualityTests.test_missing_picture_evidence_remains_null](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_decode_quality.py#L109) | pass / 0.0005 | self-contained | keep: Protects decode-confidence proxy and availability semantics; no full assertion-equivalent replacement established. |
| [DecodeQualityTests.test_inline_component_evidence_needs_no_artifact](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_decode_quality.py#L120) | pass / 0.0007 | self-contained | keep: Protects decode-confidence proxy and availability semantics; no full assertion-equivalent replacement established. |
| [DecodeQualityTests.test_incomplete_picture_does_not_penalize_received_components](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_decode_quality.py#L140) | pass / 0.0015 | self-contained | keep: Protects decode-confidence proxy and availability semantics; no full assertion-equivalent replacement established. |
| [DecodeQualityTests.test_spatial_outliers_reduce_picture_score_without_clipping](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_decode_quality.py#L154) | pass / 0.0011 | self-contained | keep: Protects decode-confidence proxy and availability semantics; no full assertion-equivalent replacement established. |

## test_mfsk_accuracy.py

text/event/raster scoring and alignment.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [FramedTextTests.test_concatenates_only_complete_payload_epochs](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L20) | pass / 0.0 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [FramedTextTests.test_unmatched_controls_are_diagnostics_not_payload](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L30) | pass / 0.0 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [FramedTextTests.test_presentation_normalization_ignores_line_wrapping](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L36) | pass / 0.0 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [FramedTextTests.test_text_score_separates_error_kinds](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L42) | pass / 0.0001 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [FramedTextTests.test_mode_sequence_reports_missed_and_false_events](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L48) | pass / 0.0001 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [PictureAccuracyTests.test_rgb_wire_order_is_row_plane_order](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L64) | pass / 0.0003 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [PictureAccuracyTests.test_declared_missing_truth_is_not_an_artifact_failure](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L74) | pass / 0.0 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [PictureAccuracyTests.test_raw_raster_metrics_report_signed_channel_bias](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L88) | pass / 0.0001 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [PictureAccuracyTests.test_alignment_finds_persistent_one_component_shift](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L99) | pass / 0.003 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |
| [PictureAccuracyTests.test_noise_does_not_force_offset_changes](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy.py#L110) | pass / 0.0033 | self-contained | keep: Protects text/event/raster scoring and alignment; no full assertion-equivalent replacement established. |

## test_mfsk_accuracy_cli.py

scoring/report CLI and gate arithmetic.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [AccuracyCliTests.test_program_fldigi_accepts_an_immutable_recent_reference](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy_cli.py#L14) | pass / 0.0031 | self-contained | keep: Protects scoring/report CLI and gate arithmetic; no full assertion-equivalent replacement established. |
| [AccuracyCliTests.test_text_command_writes_framing_diagnostics](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy_cli.py#L70) | pass / 0.0013 | self-contained | keep: Protects scoring/report CLI and gate arithmetic; no full assertion-equivalent replacement established. |
| [AccuracyCliTests.test_picture_command_scores_identical_png](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy_cli.py#L94) | pass / 0.0025 | self-contained | keep: Protects scoring/report CLI and gate arithmetic; no full assertion-equivalent replacement established. |
| [AccuracyCliTests.test_program_direct_merges_modes_and_labels_two_pass_result](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy_cli.py#L118) | pass / 0.0047 | self-contained | keep: Protects scoring/report CLI and gate arithmetic; no full assertion-equivalent replacement established. |
| [AccuracyCliTests.test_baseline_summary_retains_hash_and_headline_metrics](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy_cli.py#L324) | pass / 0.0016 | self-contained | keep: Protects scoring/report CLI and gate arithmetic; no full assertion-equivalent replacement established. |
| [AccuracyCliTests.test_planning_gate_is_hierarchical_and_enforces_regression_limits](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy_cli.py#L418) | pass / 0.0014 | self-contained | keep: Protects scoring/report CLI and gate arithmetic; no full assertion-equivalent replacement established. |
| [AccuracyCliTests.test_planning_gate_is_not_computable_with_an_unpaired_case](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_accuracy_cli.py#L497) | pass / 0.0014 | self-contained | keep: Protects scoring/report CLI and gate arithmetic; no full assertion-equivalent replacement established. |

## test_mfsk_corpus.py

corpus inventory, promotion and integrity.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [ReceivedCorpusTests.test_inventory_measures_complete_capture_and_excludes_output](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_corpus.py#L39) | pass / 0.008 | self-contained | keep: Protects corpus inventory, promotion and integrity; no full assertion-equivalent replacement established. |
| [ReceivedCorpusTests.test_promotion_is_self_contained_and_verifiable](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_corpus.py#L55) | pass / 0.0031 | self-contained | keep: Protects corpus inventory, promotion and integrity; no full assertion-equivalent replacement established. |
| [ReceivedCorpusTests.test_verifier_rejects_missing_scorecard](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_corpus.py#L94) | pass / 0.0005 | self-contained | keep: Protects corpus inventory, promotion and integrity; no full assertion-equivalent replacement established. |
| [ReceivedCorpusTests.test_verifier_allows_explicitly_missing_picture_truth](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_corpus.py#L121) | pass / 0.001 | self-contained | keep: Protects corpus inventory, promotion and integrity; no full assertion-equivalent replacement established. |

## test_mfsk_decode_remediation_r1.py

RSID evidence and acquisition.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [RemediationR1Test.test_shared_detector_emits_ranked_mode_region_and_track](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r1.py#L22) | pass / 0.1047 | self-contained | keep: Protects RSID evidence and acquisition; no full assertion-equivalent replacement established. |
| [RemediationR1Test.test_auto_manifest_attempts_segmented_payload_after_r1_evidence](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r1.py#L49) | pass / 0.4131 | self-contained | keep: Protects RSID evidence and acquisition; no full assertion-equivalent replacement established. |
| [RemediationR1Test.test_weak_full_broadcasts_recover_established_mode_events](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r1.py#L70) | pass / 38.9214 | received-IQ sidecar | keep: Real-input acquisition/transition/text assertions complement synthetic cases; not paired fldigi quality gating. |

## test_mfsk_decode_remediation_r2.py

no-RSID acquisition, tracked tones and erasure.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [RemediationR2Test.test_missing_rsid_comb_retains_both_modes_and_orientations](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r2.py#L44) | pass / 0.1298 | self-contained | keep: Protects no-RSID acquisition, tracked tones and erasure; no full assertion-equivalent replacement established. |
| [RemediationR2Test.test_auto_manifest_serializes_missing_rsid_competitors](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r2.py#L70) | pass / 0.2104 | self-contained | keep: Protects no-RSID acquisition, tracked tones and erasure; no full assertion-equivalent replacement established. |
| [RemediationR2Test.test_single_adjacent_carrier_and_picture_sweep_are_not_text_combs](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r2.py#L114) | pass / 0.2544 | self-contained | keep: Protects no-RSID acquisition, tracked tones and erasure; no full assertion-equivalent replacement established. |
| [RemediationR2Test.test_tracks_drive_non_integer_intervals_and_local_oscillators](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r2.py#L142) | pass / 0.0026 | self-contained | keep: Protects no-RSID acquisition, tracked tones and erasure; no full assertion-equivalent replacement established. |
| [RemediationR2Test.test_carrier_step_fade_and_tone_interference_are_explicit](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r2.py#L198) | pass / 0.0042 | self-contained | keep: Protects no-RSID acquisition, tracked tones and erasure; no full assertion-equivalent replacement established. |
| [RemediationR2Test.test_flat_tone_evidence_becomes_neutral_llr_erasure](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r2.py#L248) | pass / 0.0032 | self-contained | keep: Protects no-RSID acquisition, tracked tones and erasure; no full assertion-equivalent replacement established. |
| [RemediationR2ReceivedTest.test_held_out_text_segments_decode_without_center_hint](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r2.py#L276) | pass / 12.6403 | received-IQ sidecar | keep: Real-input acquisition/transition/text assertions complement synthetic cases; not paired fldigi quality gating. |

## test_mfsk_decode_remediation_r3.py

state, grammar, dropout and provenance.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [RemediationR3StateTests.test_deinterleaver_checkpoint_restore_and_fill_validity](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r3.py#L23) | pass / 0.0002 | self-contained | keep: Protects state, grammar, dropout and provenance; no full assertion-equivalent replacement established. |
| [RemediationR3StateTests.test_unknown_viterbi_start_recovers_midstream_without_invented_reset](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r3.py#L41) | pass / 0.0019 | self-contained | keep: Protects state, grammar, dropout and provenance; no full assertion-equivalent replacement established. |
| [RemediationR3StateTests.test_varicode_checkpoint_is_chunk_equivalent_and_has_provenance](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r3.py#L54) | pass / 0.0003 | self-contained | consolidate: Overlap with newer checkpoint test; transfer confidence and source-bit interval assertions before retiring this method. Destination: test_mfsk_decode_session11c.Session11CStateCarrySpikeTests.test_varicode_source_coordinates_survive_checkpoint |
| [RemediationR3StateTests.test_confidence_aware_header_rejects_damage_and_accepts_split_token](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r3.py#L73) | pass / 0.0001 | self-contained | keep: Protects state, grammar, dropout and provenance; no full assertion-equivalent replacement established. |
| [RemediationR3StateTests.test_sustained_dropout_creates_explicit_new_epoch](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r3.py#L115) | pass / 0.0001 | self-contained | keep: Protects state, grammar, dropout and provenance; no full assertion-equivalent replacement established. |
| [RemediationR3ReceivedTest.test_received_cut_without_nearby_rsid_records_independent_epoch](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r3.py#L142) | pass / 5.7159 | received-IQ sidecar | keep: Real-input acquisition/transition/text assertions complement synthetic cases; not paired fldigi quality gating. |

## test_mfsk_decode_remediation_r4.py

fractional picture clocks, drift and boundaries.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [RemediationR4PictureEvidenceTests.test_fractional_p2_p4_p8_clock_and_ranked_boundaries](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r4.py#L47) | pass / 0.0373 | self-contained | keep: Protects fractional picture clocks, drift and boundaries; no full assertion-equivalent replacement established. |
| [RemediationR4PictureEvidenceTests.test_offset_drift_step_and_content_bias_matrix](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r4.py#L116) | pass / 0.1617 | self-contained | keep: Protects fractional picture clocks, drift and boundaries; no full assertion-equivalent replacement established. |

## test_mfsk_decode_remediation_r5.py

bounded text integration.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [BoundedPipelineTests.test_controlled_text_can_use_bounded_organization](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_remediation_r5.py#L19) | skip / 0.0001 | missing independent controlled recordings | repair: Unavailable original pinned transmitter recordings; independent interoperability assertion is not supplied by coupled GramPy round trips. Destination: Maintained integration input plus assertions that bounded branch runs and known text survives; independent coverage separately. |

## test_mfsk_decode_session1.py

coordinates, wire primitives and SigMF contracts.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [CoordinateTests.test_rational_resampling_round_trip_and_ties_to_even](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L34) | pass / 0.0 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [CoordinateTests.test_composition_retains_exact_ratio_and_uncertainty](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L44) | pass / 0.0001 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [WirePrimitiveTests.test_convolutional_encoder_matches_all_fixed_vectors](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L63) | pass / 0.0001 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [WirePrimitiveTests.test_gray_mapping_matches_composed_fixed_vector](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L68) | pass / 0.0 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [WirePrimitiveTests.test_tone_metrics_produce_transmitted_lane_llrs](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L77) | pass / 0.0018 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [WirePrimitiveTests.test_soft_deinterleaver_recovers_groups_after_fixed_delay](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L93) | pass / 0.0002 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [SigmfHarnessTests.test_cli_emits_schema_valid_atomic_manifest_without_intermediates](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L114) | pass / 0.9336 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [SigmfHarnessTests.test_cf32_nonfinite_and_ci16_clipping_are_reported](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L173) | pass / 0.0206 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [SigmfHarnessTests.test_malformed_and_misaligned_inputs_are_rejected](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L197) | pass / 0.0014 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [SigmfHarnessTests.test_capture_must_establish_requested_interval](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L208) | pass / 0.001 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |
| [SigmfHarnessTests.test_trim_ancestry_is_explicit_and_input_coordinates_stay_identity](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session1.py#L216) | pass / 0.0005 | self-contained | keep: Protects coordinates, wire primitives and SigMF contracts; no full assertion-equivalent replacement established. |

## test_mfsk_decode_session10b.py

supported estimators and picture/header coordination.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [PictureComponentEstimatorExperimentTests.test_phase_difference_meets_p2_p4_p8_value_and_ramp_acceptance](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L54) | pass / 0.0017 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureComponentEstimatorExperimentTests.test_phase_difference_is_stable_under_deterministic_ci16_quantization](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L73) | pass / 0.0006 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureComponentEstimatorExperimentTests.test_experiment_compares_all_predeclared_estimators](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L107) | pass / 0.0082 | self-contained | rewrite: Supported estimator correctness matters; relative ranking on one artificial ramp should not prohibit another estimator improving. Destination: Per-estimator correctness limits on declared independent patterns, retaining supported alternatives. |
| [PictureComponentEstimatorExperimentTests.test_unknown_estimator_is_rejected](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L117) | pass / 0.0001 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureComponentEstimatorExperimentTests.test_session10e_component_windows_preserve_clean_p8_ramp](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L123) | pass / 0.0109 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureComponentEstimatorExperimentTests.test_session10e_unknown_component_window_is_rejected](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L150) | pass / 0.0002 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureComponentEstimatorExperimentTests.test_session10e_response_matched_filter_preserves_picture_endpoints](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L165) | pass / 0.0126 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureComponentEstimatorExperimentTests.test_fractional_clock_batches_equal_width_component_runs](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L201) | pass / 0.0504 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureCoordinatorTests.test_damaged_landmarks_trigger_exact_local_recovery](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L255) | pass / 0.0028 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureCoordinatorTests.test_landmark_without_exact_local_header_does_not_create_picture](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L303) | pass / 0.0039 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureCoordinatorTests.test_damaged_header_retries_at_half_symbol_alignment](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L336) | pass / 0.001 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |
| [PictureCoordinatorTests.test_suppresses_only_events_inside_accepted_picture_interval](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10b.py#L379) | pass / 0.0 | self-contained | keep: Protects supported estimators and picture/header coordination; no full assertion-equivalent replacement established. |

## test_mfsk_decode_session10c.py

persistent-tone diagnostics.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [PersistentToneMeasurementTests.test_predeclared_feature_detects_nonwinning_persistent_tone](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10c.py#L11) | pass / 0.0001 | self-contained | keep: Protects persistent-tone diagnostics; no full assertion-equivalent replacement established. |
| [PersistentToneMeasurementTests.test_legitimate_repeated_winner_is_not_its_own_competitor](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10c.py#L24) | pass / 0.0002 | self-contained | keep: Protects persistent-tone diagnostics; no full assertion-equivalent replacement established. |
| [PersistentToneMeasurementTests.test_adjacent_competition_is_measured_without_changing_metrics](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10c.py#L33) | pass / 0.0003 | self-contained | keep: Protects persistent-tone diagnostics; no full assertion-equivalent replacement established. |
| [PersistentToneMeasurementTests.test_unknown_policy_is_rejected_at_public_boundary](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10c.py#L47) | pass / 0.0001 | self-contained | keep: Protects persistent-tone diagnostics; no full assertion-equivalent replacement established. |

## test_mfsk_decode_session10f.py

protocol flush and maintained boundary/clock guards.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [ProtocolPictureBoundaryTests.test_forward_interleaver_uses_fldigi_lane_delays](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L47) | pass / 0.0001 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_flush_tone_vector_accounts_for_coded_bit_accumulator](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L60) | pass / 0.0004 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_group_phase_offsets_account_for_recognition_lane](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L74) | pass / 0.0 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_header_parser_retains_final_decoded_bit_phase](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L80) | pass / 0.0 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_header_event_carries_compact_flush_reconstruction](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L87) | pass / 0.0004 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_prediction_is_explicitly_non_operative_and_uncertain](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L94) | pass / 0.0 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_experimental_change_score_recovers_synthetic_boundary](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L110) | pass / 0.0614 | self-contained | keep: Historical name, but called function remains the production unified-grid local change guard; keep and rename. |
| [ProtocolPictureBoundaryTests.test_unified_boundary_estimator_is_the_only_supported_policy](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L156) | pass / 0.0006 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_known_flush_crossovers_recover_constructed_grid](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L167) | pass / 0.0033 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_global_crossover_clock_recovers_constructed_symbol_grid](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L211) | pass / 0.0062 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_unified_grid_uses_local_flush_to_correct_global_phase](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L257) | pass / 0.0034 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_unified_grid_increases_variance_when_flush_is_missing](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L328) | pass / 0.0003 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_unified_grid_robustly_uses_partial_damaged_flush](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L356) | pass / 0.0009 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |
| [ProtocolPictureBoundaryTests.test_global_grid_selects_semantic_start_before_leading_zeros](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session10f.py#L434) | pass / 0.0309 | self-contained | keep: Protects protocol flush and maintained boundary/clock guards; no full assertion-equivalent replacement established. |

## test_mfsk_decode_session11c.py

stateful chunk equivalence and bounded checkpoint state.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session11CStateCarrySpikeTests.test_vectorized_viterbi_step_matches_scalar_tie_semantics](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L39) | pass / 0.0467 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_sustained_loss_is_chunk_equivalent_and_bounds_contamination](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L78) | pass / 0.1088 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_track_measurement_uses_bounded_random_access](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L173) | pass / 0.0353 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_fixed_track_iq_observer_is_sample_split_equivalent](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L236) | pass / 0.0059 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_varicode_source_coordinates_survive_checkpoint](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L318) | pass / 0.0005 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_header_checkpoint_is_transactional_and_coordinate_aware](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L343) | pass / 0.0002 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_viterbi_checkpoint_is_chunk_and_batch_equivalent](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L385) | pass / 0.0254 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_checkpoint_rollback_contains_a_damaged_chunk](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L415) | pass / 0.0053 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_checkpoint_working_set_stays_bounded_by_traceback](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L436) | pass / 0.0905 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |
| [Session11CStateCarrySpikeTests.test_deinterleaver_fec_and_varicode_restore_mid_header](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11c.py#L450) | pass / 0.0058 | self-contained | keep: Protects stateful chunk equivalence and bounded checkpoint state; no full assertion-equivalent replacement established. |

## test_mfsk_decode_session11e.py

parallel ranges, compact state and bounded routing.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session11EPictureRangeTests.test_one_and_multiple_workers_are_exact_to_whole_filter](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L103) | pass / 0.1808 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_ranges_cover_indices_once_and_preserve_color_order](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L147) | pass / 0.0018 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_first_and_last_recording_edges_and_component_speeds](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L165) | pass / 0.5569 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_cancellation_and_worker_failure_are_explicit](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L206) | pass / 0.0033 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_in_flight_depth_is_independent_of_worker_count](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L223) | pass / 0.0489 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_configuration_exposes_three_separate_controls](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L248) | pass / 0.0021 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_large_picture_beyond_received_corpus_stays_range_bounded](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L258) | pass / 4.2559 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_text_epochs_close_only_at_explicit_semantic_boundaries](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L308) | pass / 0.0018 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_text_observer_and_receiver_rollback_as_one_transaction](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L325) | pass / 0.0051 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_picture_interval_advances_track_without_decoding_raster](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L351) | pass / 0.0038 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_compact_track_plan_uses_bounded_recording_reads](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L375) | pass / 0.0422 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_compact_picture_flush_state_is_exact_to_full_prefix](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L391) | pass / 0.0201 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_public_adapter_preserves_frozen_nominal_coordinates](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L406) | pass / 0.0019 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_long_resolved_fixed_mode_routes_to_compact_p11d](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L437) | pass / 0.0022 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |
| [Session11EPictureRangeTests.test_supported_hybrid_routes_only_qualified_mfsk64_to_p11d](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session11e.py#L460) | pass / 0.0022 | self-contained | keep: Protects parallel ranges, compact state and bounded routing; no full assertion-equivalent replacement established. |

## test_mfsk_decode_session12a.py

approved API/CLI defaults.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session12ADefaultTests.test_decode_config_uses_approved_picture_measurement](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session12a.py#L12) | pass / 0.0 | self-contained | keep: Protects approved API/CLI defaults; no full assertion-equivalent replacement established. |
| [Session12ADefaultTests.test_cli_uses_approved_picture_measurement](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session12a.py#L19) | pass / 0.0003 | self-contained | keep: Protects approved API/CLI defaults; no full assertion-equivalent replacement established. |

## test_mfsk_decode_session3.py

FEC/Varicode and independent MFSK32 transmission.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session3WireTests.test_soft_viterbi_recovers_fixed_encoded_bits](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session3.py#L28) | pass / 0.0003 | self-contained | keep: Protects FEC/Varicode and independent MFSK32 transmission; no full assertion-equivalent replacement established. |
| [Session3WireTests.test_varicode_parser_uses_lookahead_and_retains_invalid_words](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session3.py#L36) | pass / 0.0002 | self-contained | keep: Protects FEC/Varicode and independent MFSK32 transmission; no full assertion-equivalent replacement established. |
| [ControlledMFSK32VerticalSliceTests.test_pinned_iq_decodes_to_exact_final_octets_with_coordinates](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session3.py#L47) | skip / 0.0001 | missing independent controlled recordings | repair: Unavailable original pinned transmitter recordings; independent interoperability assertion is not supplied by coupled GramPy round trips. Destination: Validated independent fixtures in maintained sidecar; update recording-specific evidence explicitly. |

## test_mfsk_decode_session4.py

received MFSK32 text and RF tracking.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [ReceivedMFSK32AcquisitionTests.test_untouched_wrmi_interval_decodes_with_rf_tracking](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session4.py#L33) | pass / 5.5157 | received-IQ sidecar | keep: Real-input acquisition/transition/text assertions complement synthetic cases; not paired fldigi quality gating. |

## test_mfsk_decode_session5.py

controlled and received MFSK64 text.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [MFSK64TextVerticalSliceTests.test_controlled_iq_decodes_exact_octets_through_shared_pipeline](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session5.py#L31) | skip / 0.0001 | missing independent controlled recordings | repair: Unavailable original pinned transmitter recordings; independent interoperability assertion is not supplied by coupled GramPy round trips. Destination: Validated independent fixtures in maintained sidecar; update recording-specific evidence explicitly. |
| [MFSK64TextVerticalSliceTests.test_untouched_received_interval_decodes_mfsk64_without_hints](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session5.py#L74) | pass / 7.6794 | received-IQ sidecar | keep: Real-input acquisition/transition/text assertions complement synthetic cases; not paired fldigi quality gating. |

## test_mfsk_decode_session6.py

picture grammar, component clocks and controlled pictures.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [PictureHeaderTests.test_accepts_all_wire_forms_and_rejects_invalid_values](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session6.py#L53) | pass / 0.0001 | self-contained | keep: Protects picture grammar, component clocks and controlled pictures; no full assertion-equivalent replacement established. |
| [PictureHeaderTests.test_p2_p4_p8_component_clock_and_mapping](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session6.py#L75) | pass / 0.0403 | self-contained | keep: Protects picture grammar, component clocks and controlled pictures; no full assertion-equivalent replacement established. |
| [PictureHeaderTests.test_picture_mapping_uses_local_frequency_track](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session6.py#L122) | pass / 0.0167 | self-contained | keep: Protects picture grammar, component clocks and controlled pictures; no full assertion-equivalent replacement established. |
| [ControlledPictureVerticalSliceTests.test_grayscale_header_transition_and_complete_raster](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session6.py#L190) | skip / 0.0 | missing independent controlled recordings | repair: Unavailable original pinned transmitter recordings; independent interoperability assertion is not supplied by coupled GramPy round trips. Destination: Validated independent fixtures in maintained sidecar; update recording-specific evidence explicitly. |
| [ControlledPictureVerticalSliceTests.test_color_header_row_plane_assembly_and_reacquisition](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session6.py#L203) | skip / 0.0001 | missing independent controlled recordings | repair: Unavailable original pinned transmitter recordings; independent interoperability assertion is not supplied by coupled GramPy round trips. Destination: Validated independent fixtures in maintained sidecar; update recording-specific evidence explicitly. |

## test_mfsk_decode_session7.py

picture sidecar integrity and received transition.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [BoundedPictureArtifactTests.test_large_raster_and_component_planes_are_atomic_sidecars](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session7.py#L57) | pass / 0.1417 | self-contained | keep: Protects picture sidecar integrity and received transition; no full assertion-equivalent replacement established. |
| [ReceivedPictureTransitionTests.test_received_color_picture_completes_and_returns_to_text](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_decode_session7.py#L115) | pass / 17.9687 | received-IQ sidecar | keep: Real-input acquisition/transition/text assertions complement synthetic cases; not paired fldigi quality gating. |

## test_mfsk_encode_session2.py

stateful byte-to-tone encoder.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [MfskTextToneEncoderTests.test_mode_parameters_match_frozen_wire_vectors](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L37) | pass / 0.0 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_all_varicode_octets_match_the_frozen_table](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L68) | pass / 0.0011 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_every_convolutional_vector_matches_through_candidate_state](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L76) | pass / 0.0002 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_short_text_vector_matches_every_intermediate_and_tone](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L89) | pass / 0.0 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_all_binary_labels_map_to_exact_physical_tones](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L109) | pass / 0.0 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_all_octets_cover_steady_state_interleaving](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L115) | pass / 0.0058 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_chunk_boundaries_do_not_change_tones_or_final_state](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L133) | pass / 0.8702 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_modes_share_logical_tones_but_not_physical_parameters](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L156) | pass / 0.0004 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_partial_group_is_retained_and_completed_without_implicit_flush](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L166) | pass / 0.0 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_checkpoint_restore_is_exact_across_a_partial_group](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L182) | pass / 0.0021 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_malformed_checkpoints_are_rejected](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L203) | pass / 0.0002 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_input_validation_does_not_mutate_state](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L219) | pass / 0.0 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |
| [MfskTextToneEncoderTests.test_long_input_retains_fixed_interleaver_history](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session2.py#L231) | pass / 0.1262 | self-contained | keep: Protects stateful byte-to-tone encoder; no full assertion-equivalent replacement established. |

## test_mfsk_encode_session3.py

framing, PCM/WAV and failure cleanup.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session3FramingTests.test_complete_framing_matches_independent_oracle_in_both_modes](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L65) | pass / 0.0034 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3FramingTests.test_text_item_chunking_is_wire_invariant](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L73) | pass / 0.0015 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3FramingTests.test_plan_has_exact_frames_and_logical_item_boundaries](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L83) | pass / 0.0005 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3SynthesisTests.test_frequency_formula_and_every_supported_output_rate](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L102) | pass / 0.0661 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3SynthesisTests.test_phase_is_continuous_and_matches_integrated_frequency](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L126) | pass / 0.0012 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3SynthesisTests.test_pcm_level_and_frame_neutral_raised_cosine_envelope](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L160) | pass / 0.0018 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3SynthesisTests.test_pcm_quantization_has_exact_initial_samples](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L186) | pass / 0.0042 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3SynthesisTests.test_pcm_writes_remain_one_symbol_bounded_for_long_tone_streams](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L207) | pass / 0.2506 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3WaveTests.test_streaming_output_is_canonical_wav_with_exact_duration](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L230) | pass / 0.042 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3WaveTests.test_invalid_preflight_preserves_existing_output](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L256) | pass / 0.0009 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3WaveTests.test_reported_write_failure_removes_replaced_output](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L270) | pass / 0.0013 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3WaveTests.test_validation_boundaries](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L306) | pass / 0.0 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |
| [Session3WaveTests.test_coupled_round_trip_recovers_payload_in_both_modes](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session3.py#L315) | pass / 0.6338 | self-contained | keep: Protects framing, PCM/WAV and failure cleanup; no full assertion-equivalent replacement established. |

## test_mfsk_encode_session4.py

image normalization, raster order and preflight.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session4PictureTests.test_l_and_rgb_normalization_have_exact_component_order](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session4.py#L26) | pass / 0.0013 | self-contained | keep: Protects image normalization, raster order and preflight; no full assertion-equivalent replacement established. |
| [Session4PictureTests.test_l_color_public_wav_matches_equivalent_rgb_in_both_modes_and_all_speeds](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session4.py#L47) | pass / 1.1452 | self-contained | keep: Protects image normalization, raster order and preflight; no full assertion-equivalent replacement established. |
| [Session4PictureTests.test_raster_frequencies_and_timings_are_exact_at_endpoints](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session4.py#L67) | pass / 0.0011 | self-contained | keep: Protects image normalization, raster order and preflight; no full assertion-equivalent replacement established. |
| [Session4PictureTests.test_geometry_profile_alpha_and_input_size_are_rejected](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session4.py#L84) | pass / 0.0104 | self-contained | keep: Protects image normalization, raster order and preflight; no full assertion-equivalent replacement established. |
| [Session4PictureTests.test_resource_limits_and_invalid_forms_are_checked_before_raster_output](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session4.py#L99) | pass / 0.0005 | self-contained | keep: Protects image normalization, raster order and preflight; no full assertion-equivalent replacement established. |

## test_mfsk_encode_session5.py

picture transitions, continuous phase and resumed text.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session5AnnouncementAndPlanTests.test_announcements_match_the_accepted_fldigi_convention](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session5.py#L123) | pass / 0.0011 | self-contained | keep: Protects picture transitions, continuous phase and resumed text; no full assertion-equivalent replacement established. |
| [Session5AnnouncementAndPlanTests.test_all_orderings_have_exact_independent_transition_coordinates](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session5.py#L139) | pass / 0.0082 | self-contained | keep: Protects picture transitions, continuous phase and resumed text; no full assertion-equivalent replacement established. |
| [Session5SynthesisTests.test_phase_is_continuous_across_tone_prologue_raster_and_tone](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session5.py#L205) | pass / 0.001 | self-contained | keep: Protects picture transitions, continuous phase and resumed text; no full assertion-equivalent replacement established. |
| [Session5SynthesisTests.test_complete_wav_matches_plan_for_both_modes_and_multiple_images](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session5.py#L235) | pass / 0.2654 | self-contained | keep: Protects picture transitions, continuous phase and resumed text; no full assertion-equivalent replacement established. |
| [Session5SynthesisTests.test_coupled_grampy_recovers_header_picture_and_resumed_text](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session5.py#L273) | pass / 0.5085 | self-contained | keep: Protects picture transitions, continuous phase and resumed text; no full assertion-equivalent replacement established. |

## test_mfsk_encode_session6.py

parts/composition API, input parsing and file safety.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session6CompositionTests.test_public_surface_and_text_conversion](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L35) | pass / 0.0001 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |
| [Session6CompositionTests.test_adjacent_modes_have_no_implicit_gap_and_independent_framing](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L44) | pass / 0.5506 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |
| [Session6CompositionTests.test_mixed_text_file_picture_audio_and_silence_coordinates](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L81) | pass / 0.0968 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |
| [Session6CompositionTests.test_audio_ancillary_chunk_is_skipped_and_pcm_copied_exactly](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L105) | pass / 0.0014 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |
| [Session6CompositionTests.test_preflight_preserves_existing_output_for_bad_input_and_alias](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L122) | pass / 0.0018 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |
| [Session6CompositionTests.test_malformed_audio_rejected_before_replacement](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L159) | pass / 0.0009 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |
| [Session6CompositionTests.test_truncated_png_rejected_before_replacement](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L172) | pass / 0.0313 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |
| [Session6CompositionTests.test_reported_write_failure_removes_replaced_output](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L184) | pass / 0.0006 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |
| [Session6CompositionTests.test_removal_failure_reports_residual_path_and_preserves_cause](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6.py#L193) | pass / 0.0008 | self-contained | keep: Protects parts/composition API, input parsing and file safety; no full assertion-equivalent replacement established. |

## test_mfsk_encode_session6r1.py

independent RSID PCM oracle and resource bounds.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session6R1Tests.test_streaming_peak_memory_is_bounded_at_maximum_rate](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r1.py#L47) | pass / 0.3611 | self-contained | keep: Protects independent RSID PCM oracle and resource bounds; no full assertion-equivalent replacement established. |
| [Session6R1Tests.test_complete_pcm_matches_independent_oracle_at_multiple_carriers](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r1.py#L64) | pass / 0.1041 | self-contained | keep: Protects independent RSID PCM oracle and resource bounds; no full assertion-equivalent replacement established. |
| [Session6R1Tests.test_every_supported_rate_has_exact_frames_and_symbol_bounded_writes](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r1.py#L72) | pass / 1.7283 | self-contained | keep: Protects independent RSID PCM oracle and resource bounds; no full assertion-equivalent replacement established. |
| [Session6R1Tests.test_guards_phase_reset_and_no_envelope](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r1.py#L95) | pass / 0.033 | self-contained | keep: Protects independent RSID PCM oracle and resource bounds; no full assertion-equivalent replacement established. |
| [Session6R1Tests.test_oracle_rejects_tone_carrier_timing_phase_and_level_mutations](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r1.py#L112) | pass / 0.1096 | self-contained | keep: Protects independent RSID PCM oracle and resource bounds; no full assertion-equivalent replacement established. |
| [Session6R1Tests.test_invalid_preflight_and_sink_failures](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r1.py#L135) | pass / 0.0003 | self-contained | keep: Protects independent RSID PCM oracle and resource bounds; no full assertion-equivalent replacement established. |

## test_mfsk_encode_session6r2.py

RSID composition, accounting and automatic acquisition.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session6R2Tests.test_prefix_and_existing_mfsk_pcm_join_exactly_without_extra_gap](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r2.py#L27) | pass / 0.8315 | self-contained | keep: Protects RSID composition, accounting and automatic acquisition; no full assertion-equivalent replacement established. |
| [Session6R2Tests.test_empty_items_and_every_rate_include_each_prefix_in_preflight](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r2.py#L49) | pass / 0.0477 | self-contained | keep: Protects RSID composition, accounting and automatic acquisition; no full assertion-equivalent replacement established. |
| [Session6R2Tests.test_riff_ceiling_counts_prefix_for_empty_and_repeated_segments](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r2.py#L69) | pass / 0.0026 | self-contained | keep: Protects RSID composition, accounting and automatic acquisition; no full assertion-equivalent replacement established. |
| [Session6R2Tests.test_prefix_failure_and_accounting_mismatch_remove_replaced_output](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r2.py#L83) | pass / 0.0256 | self-contained | keep: Protects RSID composition, accounting and automatic acquisition; no full assertion-equivalent replacement established. |
| [Session6R2Tests.test_repeated_empty_segments_each_emit_complete_prefix_and_framing](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r2.py#L107) | pass / 0.1818 | self-contained | keep: Protects RSID composition, accounting and automatic acquisition; no full assertion-equivalent replacement established. |
| [Session6R2Tests.test_whole_wav_auto_acquisition_and_payload_recovery](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session6r2.py#L121) | pass / 25.9127 | self-contained | keep: Protects RSID composition, accounting and automatic acquisition; no full assertion-equivalent replacement established. |

## test_mfsk_encode_session7.py

large-input streaming, coordinates and package contracts.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [Session7HardeningTests.test_distribution_metadata_public_exports_and_library_docs_agree](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session7.py#L33) | pass / 0.0018 | self-contained | split: Keep package dependencies/API exports/CLI contract; remove fragile editorial phrase requirements from runtime tests. |
| [Session7HardeningTests.test_audio_copy_and_silence_use_fixed_size_pcm_writes](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session7.py#L52) | pass / 0.0317 | self-contained | keep: Protects large-input streaming, coordinates and package contracts; no full assertion-equivalent replacement established. |
| [Session7HardeningTests.test_long_text_file_is_consumed_in_fixed_chunks](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session7.py#L76) | pass / 0.0026 | self-contained | keep: Protects large-input streaming, coordinates and package contracts; no full assertion-equivalent replacement established. |
| [Session7HardeningTests.test_large_image_keeps_one_source_raster_and_streams_components](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session7.py#L102) | pass / 1.3756 | self-contained | keep: Protects large-input streaming, coordinates and package contracts; no full assertion-equivalent replacement established. |
| [Session7HardeningTests.test_result_coordinates_match_completed_wav_after_mixed_parts](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encode_session7.py#L122) | pass / 0.096 | self-contained | keep: Protects large-input streaming, coordinates and package contracts; no full assertion-equivalent replacement established. |

## test_mfsk_encoder_evidence.py

independent encoder oracle and evidence identity.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [OfflineEncoderOracleTests.test_oracle_inputs_have_frozen_identity_and_match_packaged_copies](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L61) | pass / 0.0015 | self-contained | keep: Protects independent encoder oracle and evidence identity; no full assertion-equivalent replacement established. |
| [OfflineEncoderOracleTests.test_all_varicode_octets_are_exact_and_uniquely_terminated](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L79) | pass / 0.0009 | self-contained | keep: Protects independent encoder oracle and evidence identity; no full assertion-equivalent replacement established. |
| [OfflineEncoderOracleTests.test_every_fec_vector_matches_the_independent_equations](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L101) | pass / 0.0001 | self-contained | keep: Protects independent encoder oracle and evidence identity; no full assertion-equivalent replacement established. |
| [OfflineEncoderOracleTests.test_interleaver_and_text_to_tone_vectors_are_exact](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L109) | pass / 0.0001 | self-contained | keep: Protects independent encoder oracle and evidence identity; no full assertion-equivalent replacement established. |
| [OfflineEncoderOracleTests.test_mode_and_framing_counts_are_exact](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L142) | pass / 0.0001 | self-contained | keep: Protects independent encoder oracle and evidence identity; no full assertion-equivalent replacement established. |
| [OfflineEncoderOracleTests.test_picture_headers_prologue_raster_order_and_frequencies_are_exact](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L186) | pass / 0.0001 | self-contained | keep: Protects independent encoder oracle and evidence identity; no full assertion-equivalent replacement established. |
| [OfflineEncoderOracleTests.test_frozen_reference_wav_measurements_remain_exact](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L254) | pass / 0.0 | historical committed evidence | retire from current product suite: Only reads saved JSON constants; does not read a waveform or measure current output. Destination: Central provenance integrity check plus actual independent fixture/quality coverage. |
| [OfflineEncoderOracleTests.test_oracle_rejects_deliberate_tone_timing_and_rgb_order_defects](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L273) | pass / 0.0002 | self-contained | keep: Protects independent encoder oracle and evidence identity; no full assertion-equivalent replacement established. |
| [PiQualificationContractTests.test_matrix_has_the_required_interoperability_coverage](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L295) | pass / 0.0003 | historical committed evidence | retire from current product suite: Replace/rehome v1 matrix contract with maintained v3 coverage; historical compatibility separately if supported. Destination: Active v3 qualification contract check (not yet in standard suite). |
| [PiQualificationContractTests.test_pi_manifest_schema_is_valid_and_requires_hashes_and_outcomes](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_encoder_evidence.py#L368) | pass / 0.0191 | historical committed evidence | retire from current product suite: Historical v1 schema/synthetic record, not current qualification behavior. Destination: Active qualification record/schema validation; explicit historical workflow tests if supported. |

## test_mfsk_fixture_inventory.py

fixture availability/hash checks and path safety.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [MfskFixtureInventoryTests.test_checked_in_evidence_has_complete_controlled_fixture_matrix](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_fixture_inventory.py#L20) | pass / 0.0001 | self-contained | keep: Protects fixture availability/hash checks and path safety; no full assertion-equivalent replacement established. |
| [MfskFixtureInventoryTests.test_inventory_distinguishes_verified_missing_and_mismatch](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_fixture_inventory.py#L39) | pass / 0.0015 | self-contained | keep: Protects fixture availability/hash checks and path safety; no full assertion-equivalent replacement established. |
| [MfskFixtureInventoryTests.test_cli_missing_is_available_by_default_and_strict_on_request](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_fixture_inventory.py#L59) | pass / 0.1481 | self-contained | keep: Protects fixture availability/hash checks and path safety; no full assertion-equivalent replacement established. |
| [MfskFixtureInventoryTests.test_rejects_artifact_path_escape](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_fixture_inventory.py#L97) | pass / 0.0001 | self-contained | keep: Protects fixture availability/hash checks and path safety; no full assertion-equivalent replacement established. |
| [MfskControlledCorpusTests.test_available_pinned_artifacts_match_all_hashes](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_fixture_inventory.py#L105) | skip / 0.0003 | missing independent controlled recordings | consolidate: Missing fixture integrity check should become one strict acceptance data preflight; keep tool negative tests. Destination: Strict fixture/corpus availability and integrity preflight (not yet implemented). |

## test_mfsk_fixture_source.py

deterministic and independently decoded source images.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [MfskFixtureSourceTests.test_checked_in_png_matches_deterministic_generator](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_fixture_source.py#L19) | pass / 0.001 | self-contained | keep: Protects deterministic and independently decoded source images; no full assertion-equivalent replacement established. |
| [MfskFixtureSourceTests.test_png_contains_exact_normative_rgb_vector](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_fixture_source.py#L25) | pass / 0.0004 | self-contained | keep: Protects deterministic and independently decoded source images; no full assertion-equivalent replacement established. |

## test_mfsk_image_review.py

review/scorecard tool interface and identities.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [MfskImageReviewTests.test_candidate_specs_accept_an_arbitrary_named_set](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_image_review.py#L23) | pass / 0.0001 | self-contained | keep: Protects review/scorecard tool interface and identities; no full assertion-equivalent replacement established. |
| [MfskImageReviewTests.test_final_scorecard_preserves_identity_metrics_and_gate_status](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_image_review.py#L35) | pass / 0.0011 | self-contained | keep: Protects review/scorecard tool interface and identities; no full assertion-equivalent replacement established. |
| [MfskImageReviewTests.test_summary_and_gate_must_be_supplied_together](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_image_review.py#L126) | pass / 0.0001 | self-contained | keep: Protects review/scorecard tool interface and identities; no full assertion-equivalent replacement established. |

## test_mfsk_rsid_oracle.py

independent RSID codewords and interval arithmetic.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [RsidOracleTests.test_frozen_words_cover_primary_and_extended_identifiers](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_rsid_oracle.py#L47) | pass / 0.0003 | self-contained | keep: Protects independent RSID codewords and interval arithmetic; no full assertion-equivalent replacement established. |
| [RsidOracleTests.test_48k_prefix_intervals_are_contiguous_and_exact](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_rsid_oracle.py#L62) | pass / 0.0001 | self-contained | keep: Protects independent RSID codewords and interval arithmetic; no full assertion-equivalent replacement established. |
| [RsidOracleTests.test_draft_pi_contract_requires_continuous_rxid_acquisition](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_rsid_oracle.py#L78) | pass / 0.0169 | historical committed evidence | retire from current product suite: Historical v2 draft exact-case contract; preserve required RxID semantics in current workflow. Destination: Active whole-WAV practical qualification settings test (not yet in standard suite). |

## test_mfsk_wire_vectors.py

independent wire-vector data consistency.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [MfskWireVectorTests.test_convolutional_vectors_match_explicit_contract](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_wire_vectors.py#L19) | pass / 0.0001 | self-contained | keep: Protects independent wire-vector data consistency; no full assertion-equivalent replacement established. |
| [MfskWireVectorTests.test_fldigi_interleaver_vectors_match_closed_form_rule](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_wire_vectors.py#L37) | pass / 0.0 | self-contained | keep: Protects independent wire-vector data consistency; no full assertion-equivalent replacement established. |
| [MfskWireVectorTests.test_lettered_interleaver_example_distinguishes_orientations](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_wire_vectors.py#L49) | pass / 0.0 | self-contained | keep: Protects independent wire-vector data consistency; no full assertion-equivalent replacement established. |
| [MfskWireVectorTests.test_mode_timing_is_internally_consistent](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_wire_vectors.py#L64) | pass / 0.0 | self-contained | keep: Protects independent wire-vector data consistency; no full assertion-equivalent replacement established. |
| [MfskWireVectorTests.test_transmission_framing_counts_match_mode_parameters](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_wire_vectors.py#L74) | pass / 0.0 | self-contained | keep: Protects independent wire-vector data consistency; no full assertion-equivalent replacement established. |
| [MfskWireVectorTests.test_text_to_tones_vector_composes_independent_contracts](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_wire_vectors.py#L94) | pass / 0.0001 | self-contained | keep: Protects independent wire-vector data consistency; no full assertion-equivalent replacement established. |
| [MfskWireVectorTests.test_fixture_evidence_is_well_formed_and_independently_received](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_wire_vectors.py#L151) | pass / 0.0001 | self-contained | consolidate: Verifies metadata claims and hash syntax, not an independent receiver run; merge with maintained provenance validation preserving these fields. Destination: Central provenance checks alongside test_mfsk_fixture_inventory and packaged-data identity tests. |
| [MfskWireVectorTests.test_complete_varicode_table_has_required_structure](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_mfsk_wire_vectors.py#L168) | pass / 0.0002 | self-contained | consolidate: Table shape, terminators, uniqueness and fixed octets overlap the independent encoder-oracle test; transfer schema assertion before retiring this method. Destination: test_mfsk_encoder_evidence.OfflineEncoderOracleTests.test_all_varicode_octets_are_exact_and_uniquely_terminated (plus table schema assertion). |

## test_reception_quality.py

signal/noise measurement and unavailable values.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [ReceptionQualityTests.test_signal_fade_drift_noise_rise_and_quiet_interval](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_reception_quality.py#L48) | pass / 0.0157 | self-contained | keep: Protects signal/noise measurement and unavailable values; no full assertion-equivalent replacement established. |
| [ReceptionQualityTests.test_nonfinite_iq_has_explicit_unavailable_values](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_reception_quality.py#L79) | pass / 0.0087 | self-contained | keep: Protects signal/noise measurement and unavailable values; no full assertion-equivalent replacement established. |

## test_setup_corpus.py

corpus transfer, encryption, archive safety and failure handling.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [CorpusTransferTests.test_fetch_installs_requested_archive_without_version_synchronization](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L59) | pass / 0.0366 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_package_and_fetch_encrypted_corpus_round_trip](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L74) | pass / 0.1458 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_package_without_encryption_round_trip](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L91) | pass / 0.0254 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_package_refuses_to_overwrite_archive](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L111) | pass / 0.0006 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_wrong_password_preserves_existing_corpus](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L122) | pass / 0.1419 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_checksum_failure_preserves_existing_corpus](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L136) | pass / 0.0285 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_invalid_checksum_is_rejected_before_download](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L147) | pass / 0.0003 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_curl_failure_is_reported_without_leaving_a_corpus](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L154) | pass / 0.001 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_unsafe_archive_path_preserves_existing_corpus](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L167) | pass / 0.0155 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_missing_version_file_preserves_existing_corpus](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L180) | pass / 0.0171 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_ignores_optional_appledouble_root_metadata](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L191) | pass / 0.0187 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_symlinked_corpus_root_is_rejected](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L201) | pass / 0.0011 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |
| [CorpusTransferTests.test_fetch_script_installs_explicit_archive](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_setup_corpus.py#L214) | pass / 0.089 | self-contained | keep: Protects corpus transfer, encryption, archive safety and failure handling; no full assertion-equivalent replacement established. |

## test_text_manifest.py

text framing, Unicode and picture links.

| Method | Observed / seconds | Input tier | Recommendation and reason |
| --- | --- | --- | --- |
| [TextManifestTests.test_complete_frame_spans_picture_and_links_to_introductory_text](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_text_manifest.py#L50) | pass / 0.002 | self-contained | keep: Protects text framing, Unicode and picture links; no full assertion-equivalent replacement established. |
| [TextManifestTests.test_unframed_text_is_retained_when_no_stx_is_detected](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_text_manifest.py#L82) | pass / 0.0005 | self-contained | keep: Protects text framing, Unicode and picture links; no full assertion-equivalent replacement established. |
| [TextManifestTests.test_utf8_quotes_and_accent_with_invalid_octet_preserved](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_text_manifest.py#L92) | pass / 0.0004 | self-contained | keep: Protects text framing, Unicode and picture links; no full assertion-equivalent replacement established. |
| [TextManifestTests.test_full_broadcast_reference_has_ordered_modes_and_nine_images](https://github.com/selsamman/GramPy/blob/21263854f2ece6350fe6654ed4a70dfda4cb58ea/tests/test_text_manifest.py#L106) | pass / 0.1027 | saved GramPy manifest sidecar | reclassify: Useful saved-manifest compatibility transform; no fresh IQ decode and no fldigi comparison. |
