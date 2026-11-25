# FIX-R1 审查包 03 — 全部 Golden 夹具与全部测试

审查对象 commit：`221f902798a245b7a2672f3a53a9a63ab176e014`（tag `P032-v1.0.1`，P032 FIX-R1 重冻结，规格 v1.0.1）。
本包全部内容取自该 tag 的 git 对象（`git show <tag>:<path>`），非工作区副本；
每节标题下均给出该文件在该 tag 下的 SHA-256（对内容字节计算）。
核对方法：`git show 221f902798a245b7a2672f3a53a9a63ab176e014:<path> | sha256sum`。

## fixtures/extended/E01.json

- SHA-256：`110c4bbc5190c7e4e48f03f908cc5d80f1fdae66ddf461f952af4188ed954da8`
- 字节数：869

```
{
  "scenario_id": "E01",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Vary field name lowercase ('vary: Accept' on the wire) \u2014 normal Accept separation.",
  "origin_scenario": "vary_lowercase",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "Origin emits the Vary field name lowercase; HTTP field names are case-insensitive (RFC 9110 \u00a75.1), so the run must PASS exactly like C01. The runner lowercases header names in evidence, so the wire-level lowercase fact is pinned separately by tests/golden/test_extended.py::test_e01_vary_field_name_is_lowercase_on_the_wire."
}
```

## fixtures/extended/E02.json

- SHA-256：`a7638fa7442c2608d8b6e7037e06908d8e02dedfc286743fe31f2562446de3ed`
- 字节数：665

```
{
  "scenario_id": "E02",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Vary contains Accept and Accept-Encoding \u2014 both representations distinguished correctly.",
  "origin_scenario": "vary_multi",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "Multi-field Vary: the Accept token is present, so the proxy keys by Accept and the classifier sees Vary: Accept as present."
}
```

## fixtures/extended/E03.json

- SHA-256：`d4131dd72e1fef11dcad4e46ab7e90cf0d65d9cb65e1e6b38af530090b49e2fa`
- 字节数：917

```
{
  "scenario_id": "E03",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Vary: * \u2014 the cache cannot reuse the stored entry; the second request is a fresh fetch.",
  "origin_scenario": "vary_star",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "RFC 9111 \u00a74.1: Vary: * must never be reused. The proxy stores nothing and reports BYPASS for every proxied request; that BYPASS is compliant and exempt from the \u00a78.9 variant leg (ADR-004). Spec \u00a711.3 says 'second request MISS'; the honest \u00a75.3 label is BYPASS (MISS requires an entry to be created, and none is), and the verdict is PASS_OBSERVED either way."
}
```

## fixtures/extended/E04.json

- SHA-256：`81e3d165180eaf05fe39ea5eccad1ba8b8415b543f5c2e6c6c5f0ff5fa965cd7`
- 字节数：789

```
{
  "scenario_id": "E04",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "No Vary, manual Accept cache key \u2014 both representations correct, Vary WARNING.",
  "origin_scenario": "no_vary",
  "proxy_mode": "manual_accept_key",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 1
    },
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 2
    }
  ],
  "notes": "Same shape as C03/C04 (\u00a77.11: missing Vary alone is not a bleed when the cache separates by Accept)."
}
```

## fixtures/extended/E05.json

- SHA-256：`1ad9b6897558a71c9b67a42e6804f73cd26b99ffed9ad96fba0e8d1048456b58`
- 字节数：575

```
{
  "scenario_id": "E05",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "no-store, no Vary \u2014 both representations BYPASS.",
  "origin_scenario": "no_vary",
  "proxy_mode": "disabled",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "Disabled proxy under a no_store contract: every proxied request BYPASSes (cf. C17)."
}
```

## fixtures/extended/E06.json

- SHA-256：`b94b1f177bc85534c228e55dc6c35c470fc07a646fee860514005117d6c37b22`
- 字节数：580

```
{
  "scenario_id": "E06",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "no-store, Vary present \u2014 both representations BYPASS.",
  "origin_scenario": "healthy",
  "proxy_mode": "disabled",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "Disabled proxy under a no_store contract: every proxied request BYPASSes (cf. C18)."
}
```

## fixtures/extended/E07.json

- SHA-256：`8d2f4ab352921761f87b34571bff7b87faf1b6a8f6193d68acad9f5931962937`
- 字节数：1340

```
{
  "scenario_id": "E07",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "max-age=0 \u2014 revalidation required; the first release does not implement revalidation.",
  "origin_scenario": "cache_max_age_0",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 1,
  "expected_first_error_experiment_id": "ORIGIN_HTML",
  "expected_diagnostics": [
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 1
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 2
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 3
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 4
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 5
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 6
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 7
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 8
    }
  ],
  "notes": "\u00a78.6 limit_code revalidation_required on every response carrying Cache-Control: max-age=0 (classifier + Oracle, ADR-004). First error is request 001, the first response carrying the directive."
}
```

## fixtures/extended/E08.json

- SHA-256：`f1b40ec819c81131d2c4eb29f03c058b5182f16982fadc79e75f22a01fa358a0`
- 字节数：1342

```
{
  "scenario_id": "E08",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "no-cache \u2014 revalidation required; the first release does not implement full revalidation.",
  "origin_scenario": "cache_no_cache",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 1,
  "expected_first_error_experiment_id": "ORIGIN_HTML",
  "expected_diagnostics": [
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 1
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 2
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 3
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 4
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 5
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 6
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 7
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 8
    }
  ],
  "notes": "\u00a78.6 limit_code revalidation_required on every response carrying Cache-Control: no-cache (classifier + Oracle, ADR-004). First error is request 001, the first response carrying the directive."
}
```

## fixtures/extended/E09.json

- SHA-256：`188dc4ff69afa3571c186607195e6139f304a74c0bd1e5c2a285c6e304bcebde`
- 字节数：1099

```
{
  "scenario_id": "E09",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Origin always answers Markdown requests with the HTML Content-Type \u2014 O-M fails.",
  "origin_scenario": "markdown_wrong_content_type",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "ORIGIN_NEGOTIATION_ERROR",
  "expected_first_error": 2,
  "expected_first_error_experiment_id": "ORIGIN_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "ORIGIN_NEGOTIATION_ERROR",
      "request_index": 2
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 4
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 7
    }
  ],
  "notes": "Same shape as C08 (markdown_404), with the wrong-Content-Type fault instead of 404: the existing markdown_wrong_content_type origin fixture is the T003 'wrong representation' stand-in (Content-Type of the other representation)."
}
```

## fixtures/extended/E10.json

- SHA-256：`311de774d45bdc191adfb9e2921c0c2b630a59ac157d167b488b0552d8cfbe8d`
- 字节数：965

```
{
  "scenario_id": "E10",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Origin always answers HTML requests with the Markdown Content-Type \u2014 O-H fails.",
  "origin_scenario": "html_markdown_content_type",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "ORIGIN_NEGOTIATION_ERROR",
  "expected_first_error": 1,
  "expected_first_error_experiment_id": "ORIGIN_HTML",
  "expected_diagnostics": [
    {
      "code": "ORIGIN_NEGOTIATION_ERROR",
      "request_index": 1
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 3
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 5
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Mirror of E09/C07/C09 in the other direction (new origin fixture html_markdown_content_type.json)."
}
```

## fixtures/extended/E11.json

- SHA-256：`63db1074d8467b6b312efcd56b5a0e9d7f2f5d5793cc1a3453ccc73a652273d2`
- 字节数：956

```
{
  "scenario_id": "E11",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Origin answers Markdown requests with 406 \u2014 O-M status mismatch.",
  "origin_scenario": "markdown_406",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "ORIGIN_NEGOTIATION_ERROR",
  "expected_first_error": 2,
  "expected_first_error_experiment_id": "ORIGIN_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "ORIGIN_NEGOTIATION_ERROR",
      "request_index": 2
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 4
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 7
    }
  ],
  "notes": "Same shape as C08: the origin refuses the Markdown representation with 406 (new origin fixture markdown_406.json)."
}
```

## fixtures/extended/E12.json

- SHA-256：`8518520f76c31bbdf410dcba6c70e4a22985e4bca7429ca609bb5966ce33be82`
- 字节数：1756

```
{
  "scenario_id": "E12",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Origin returns a local redirect \u2014 the first release does not follow redirects.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_returns_local_redirect"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 3
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 3
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 4
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 4
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 5
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 5
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 6
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 6
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 7
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 7
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 8
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 8
    }
  ],
  "notes": "Harness injection (harness proxy subclass, production code untouched): every proxied GET is answered 301 with Location pointing at the loopback origin URL, without contacting the origin. \u00a78.6 limit_code redirect on 003\u2013008; no cache state can be confirmed on those requests."
}
```

## fixtures/extended/E13.json

- SHA-256：`91173ca437bf804a8963023bec6ead12a3dcb3aebf3e32797153c4148196b52c`
- 字节数：1007

```
{
  "scenario_id": "E13",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Vary present, URI-only cache, HTML first \u2014 H\u2192M confirmed HIT bleed.",
  "origin_scenario": "healthy",
  "proxy_mode": "force_uri_only",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "REPRESENTATION_BLEED",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 8
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Same shape as C11."
}
```

## fixtures/extended/E14.json

- SHA-256：`0ee1b98f44867a19afce9d7480d55f1ecd7a391954648523ecf5c99e5c504f99`
- 字节数：1121

```
{
  "scenario_id": "E14",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Vary present, URI-only cache, Markdown first \u2014 M\u2192H confirmed HIT bleed.",
  "origin_scenario": "healthy",
  "proxy_mode": "force_uri_only",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "REPRESENTATION_BLEED",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 8
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Same shape as C12 (the frozen run order always executes HTML first in each experiment; both warm orders bleed, first error 006)."
}
```

## fixtures/extended/E15.json

- SHA-256：`f7859df97a9f2fcde64f08ecffcf9d09badc79705356fb89459ebe93b3c435a7`
- 字节数：665

```
{
  "scenario_id": "E15",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "no-store, no Vary, proxy correctly BYPASSes \u2014 both orders correct.",
  "origin_scenario": "no_vary",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "A caching-capable proxy (respect_vary) bound to a no_store contract BYPASSes every request and stores nothing (cf. E05, which uses the disabled proxy)."
}
```

## fixtures/extended/E16.json

- SHA-256：`2c87f330e343856acea53e37e15d70f91dd205161598160d76d9425685a6964f`
- 字节数：670

```
{
  "scenario_id": "E16",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "no-store, Vary present, proxy correctly BYPASSes \u2014 both orders correct.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "A caching-capable proxy (respect_vary) bound to a no_store contract BYPASSes every request and stores nothing (cf. E06, which uses the disabled proxy)."
}
```

## fixtures/extended/E17.json

- SHA-256：`0a56b6e09f787a97669b600fb6fc3f89e9bec459fb0abbc88b300cb52f64d6f5`
- 字节数：1045

```
{
  "scenario_id": "E17",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Cache-Status missing, other evidence available \u2014 HIT/MISS cannot be confirmed.",
  "origin_scenario": "healthy",
  "proxy_mode": "opaque",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 3
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 4
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 5
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 6
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 7
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 8
    }
  ],
  "notes": "Same shape as C20 (opaque proxy hides the cache-status header leg)."
}
```

## fixtures/extended/E18.json

- SHA-256：`9d6c336745dcd58f37e296691cf376dce7f31a17877ee0edc3cc0fb98ef24555`
- 字节数：1148

```
{
  "scenario_id": "E18",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Origin count missing, status header present \u2014 dual proof cannot be completed.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "origin_events_unavailable"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 3
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 4
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 5
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 6
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 7
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 8
    }
  ],
  "notes": "Same shape as C21: the adjudication input carries an empty origin-event list (checked, found nothing), never None (ADR-002)."
}
```

## fixtures/extended/E19.json

- SHA-256：`a435437a49514a690ee6efdacd7c76f77c8b8ece99d1d03e659b8f5406d4ac58`
- 字节数：843

```
{
  "scenario_id": "E19",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "HIT header conflicts with the origin request record \u2014 evidence contradiction.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_lies_hit_on_warm_second"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "CACHE_EVIDENCE_CONFLICT",
      "request_index": 6
    }
  ],
  "notes": "Same shape as C22: the 4th proxied GET (006) claims HIT while the origin counter moved +1 (the body itself is the correct Markdown body, so no Sentinel/contract diagnostic fires)."
}
```

## fixtures/extended/E20.json

- SHA-256：`f607e45612c9d3fd8ccece0e9604c8d06633645bf37017fa2f20fb2f36aeb981`
- 字节数：990

```
{
  "scenario_id": "E20",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "MISS header conflicts with the origin count \u2014 evidence contradiction.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_lies_miss_with_stash_replay"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "CACHE_EVIDENCE_CONFLICT",
      "request_index": 6
    }
  ],
  "notes": "Harness injection (harness proxy subclass, production code untouched): the 4th proxied GET (006) replays the Markdown body observed at 004 without contacting the origin (counter delta 0) while claiming MISS. The replayed body is the genuine origin body, so no Sentinel/contract diagnostic fires \u2014 only the \u00a78.8 conflict."
}
```

## fixtures/extended/E21.json

- SHA-256：`f0f93fb1b23fb85d9fc9c51394cf9c2335c50c25dc8be08900a48030cdbcd315`
- 字节数：1366

```
{
  "scenario_id": "E21",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Body exceeds 1 MiB \u2014 beyond the first-release limit.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_returns_oversize_body"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 3
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 4
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 5
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 6
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 7
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 8
    }
  ],
  "notes": "Harness injection (harness proxy subclass, production code untouched): every proxied body is padded past 1 MiB with the Sentinel intact; the stored entries keep the original bodies. \u00a78.6 limit_code body_too_large on 003\u2013008 (baselines are direct-origin and small). The classifier's size check runs only because the harness passes run.raw_observations (ADR-002)."
}
```

## fixtures/extended/E22.json

- SHA-256：`24c1dd4ca46026d3fc486f48fd73030be50e61db2984a424665848d7577268e3`
- 字节数：1737

```
{
  "scenario_id": "E22",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Redirect points at a non-loopback address \u2014 following is forbidden.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_returns_external_redirect"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 3
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 3
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 4
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 4
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 5
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 5
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 6
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 6
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 7
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 7
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 8
    },
    {
      "code": "INCONCLUSIVE_LIMIT",
      "request_index": 8
    }
  ],
  "notes": "Harness injection (harness proxy subclass, production code untouched): every proxied GET is answered 301 with Location http://example.com/doc (a synthetic fixture address, never a real user URL), without contacting the origin. \u00a78.6 limit_code redirect on 003\u2013008."
}
```

## fixtures/extended/E23.json

- SHA-256：`4df8149ea2c4d06260508ec0025c4a4c119c27f487b89f62cae8be4cbd297c4d`
- 字节数：1033

```
{
  "scenario_id": "E23",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Origin healthy, proxy returns a conflicting Content-Type \u2014 the proxy response violates the contract.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_rewrites_html_content_type"
  },
  "expected_verdict": "CONTRACT_MISMATCH",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 3
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 5
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "C24 mirror for HTML: proxied HTML responses (003, 005, 008) claim Content-Type text/markdown while the body is unchanged; baselines stay correct, so this is a proxy contract violation, not an origin error."
}
```

## fixtures/extended/E24.json

- SHA-256：`de834c4bacf686097612ae54cb79884187399aab0a6555ef6973a980f79ce47c`
- 字节数：1075

```
{
  "scenario_id": "E24",
  "spec": "PROJECT_BOOK.md \u00a711.3",
  "description": "Origin healthy, proxy warm response has a wrong Sentinel \u2014 the warm body violates the contract.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_corrupts_warm_second_sentinel"
  },
  "expected_verdict": "CONTRACT_MISMATCH",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Harness injection (harness proxy subclass, production code untouched): the warm-second responses (006, 008) are returned with their Sentinel bytes replaced; stored entries keep the correct bodies, so this is not a bleed (body hashes differ from the first requests') and not an origin error (baselines stay correct)."
}
```

## fixtures/origin/cache_max_age_0.json

- SHA-256：`689648dddea694de3a956f8c4dd597e05d494f55488d34d7690d01a3e35ad3ae`
- 字节数：526

```
{"description":"E07 origin: Cache-Control: max-age=0 on every response — a cached copy needs revalidation, which the first release does not implement (§8.6 revalidation_required).","path":"/doc","representations":{"html":{"cache_control":"max-age=0","content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept"},"markdown":{"cache_control":"max-age=0","content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept"}},"scenario_id":"cache_max_age_0"}
```

## fixtures/origin/cache_no_cache.json

- SHA-256：`733ece66df859a8881ba3c3f4544e2daba9322ed9342f333ef313e6ea2ade7de`
- 字节数：522

```
{"description":"E08 origin: Cache-Control: no-cache on every response — a cached copy needs revalidation, which the first release does not implement (§8.6 revalidation_required).","path":"/doc","representations":{"html":{"cache_control":"no-cache","content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept"},"markdown":{"cache_control":"no-cache","content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept"}},"scenario_id":"cache_no_cache"}
```

## fixtures/origin/healthy.json

- SHA-256：`781d5cbbc45c14ad0e88c7e54a516625d229d29e63d659650a9f7077468569e2`
- 字节数：461

```
{"description":"Healthy synthetic origin: HTML and Markdown both 200 with the frozen Content-Type, correct Sentinel and Vary: Accept (PROJECT_BOOK §5.1.2, §11.2 C01/C02 baseline).","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"}},"scenario_id":"healthy"}
```

## fixtures/origin/html_404.json

- SHA-256：`9de4c8c93d405f2b382e27a030d3525a9c8cfa91c00c9d7a97e9028bd48137de`
- 字节数：424

```
{"description":"Status fault: HTML requests return 404 while Markdown stays 200. Expected verdict ORIGIN_NEGOTIATION_ERROR (§8.1, §11.2 C07).","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":404,"vary":"accept"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"}},"scenario_id":"html_404"}
```

## fixtures/origin/html_markdown_content_type.json

- SHA-256：`dc8dcb8fd05c986657906d9030b871e4b9e139ac82dd75dc8fbc987f114b8e25`
- 字节数：541

```
{"description":"E10 origin: HTML requests are answered with the Markdown Content-Type (the other representation's type), mirroring markdown_wrong_content_type.json in the other direction. Expected verdict ORIGIN_NEGOTIATION_ERROR (§8.1).","path":"/doc","representations":{"html":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept"}},"scenario_id":"html_markdown_content_type"}
```

## fixtures/origin/html_sentinel_wrong.json

- SHA-256：`2697aaefd3ea68fef9d24ee0348e2f2404aeeb4d2a97eb5e4fdb448c8e5406ed`
- 字节数：502

```
{"description":"Sentinel fault: HTML body contains AT_HTML_SENTINEL_999 instead of the frozen AT_HTML_SENTINEL_001 (status and Content-Type stay correct). Expected verdict ORIGIN_NEGOTIATION_ERROR (§8.1, §8.5).","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"wrong","status":200,"vary":"accept"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"}},"scenario_id":"html_sentinel_wrong"}
```

## fixtures/origin/html_wrong_content_type.json

- SHA-256：`fa26f9ecc668db0252b2bb62d1c6c7b36781c2b62059600afc3dd4530ef745dd`
- 字节数：449

```
{"description":"Content-Type fault: HTML requests return 200 but Content-Type text/plain. Expected verdict ORIGIN_NEGOTIATION_ERROR (§8.1, §11.2 C09).","path":"/doc","representations":{"html":{"content_type":"text/plain; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"}},"scenario_id":"html_wrong_content_type"}
```

## fixtures/origin/markdown_404.json

- SHA-256：`ab4a5e1cc939568c43b70f27462c6aeb7edc9bf3e2356302b71a7c374c1aa3ed`
- 字节数：441

```
{"description":"Status fault (E02-shaped): Markdown requests return 404 while HTML stays 200. Expected verdict ORIGIN_NEGOTIATION_ERROR (§8.1, §11.2 C08).","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":404,"vary":"accept"}},"scenario_id":"markdown_404"}
```

## fixtures/origin/markdown_406.json

- SHA-256：`d3446f2cd86a2da64efdc8fdb911ba0317bb301c0acf20899a78692f467583dd`
- 字节数：487

```
{"description":"E11 origin: Markdown requests are answered 406 (the origin refuses the Markdown representation). Expected verdict ORIGIN_NEGOTIATION_ERROR (§8.1); the 406 is served with a plain-text body.","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept"},"markdown":{"content_type":"text/plain; charset=utf-8","sentinel_mode":"correct","status":406,"vary":"Accept"}},"scenario_id":"markdown_406"}
```

## fixtures/origin/markdown_sentinel_missing.json

- SHA-256：`d7969598b914c5d18a90fce36cf39185e7df2195463f5987a5118c159e05f0f6`
- 字节数：481

```
{"description":"Sentinel fault: Markdown body contains no Sentinel at all (status and Content-Type stay correct). Expected verdict ORIGIN_NEGOTIATION_ERROR (§8.1, §8.5, §11.2 C10).","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"missing","status":200,"vary":"accept"}},"scenario_id":"markdown_sentinel_missing"}
```

## fixtures/origin/markdown_wrong_content_type.json

- SHA-256：`5f711669aa21c0877528f33ae1ee1895f71276f26ce7e4bd95a1e76d08366a44`
- 字节数：540

```
{"description":"Content-Type fault: Markdown requests return 200 but Content-Type text/html (the other representation's type). Expected verdict ORIGIN_NEGOTIATION_ERROR (§8.1; cf. §11.2 C24 where the proxy, not the origin, rewrites the type).","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"},"markdown":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"accept"}},"scenario_id":"markdown_wrong_content_type"}
```

## fixtures/origin/no_vary.json

- SHA-256：`e5bcadae6104f20f64ae9176cad1ac5dd671b86f0209a3de51229003954717b8`
- 字节数：467

```
{"description":"Healthy bodies with no Vary header at all. Used by the §7.11 / §11.2 C03-C04 healthy对照: missing Vary alone must not be treated as a fault when the cache separates by Accept.","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":null},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":null}},"scenario_id":"no_vary"}
```

## fixtures/origin/vary_lowercase.json

- SHA-256：`ace6dd4433670c4822378b900c1a9364d8625afac1beef4150844a05e0b7ac04`
- 字节数：592

```
{"description":"E01 origin: Vary field name lowercase ('vary: Accept' on the wire, RFC 9110 §5.1 field names are case-insensitive). Bodies, status and Content-Type are healthy; the proxy and classifier must treat the lowercase name exactly like 'Vary'.","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept","vary_header_name":"vary"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept","vary_header_name":"vary"}},"scenario_id":"vary_lowercase"}
```

## fixtures/origin/vary_multi.json

- SHA-256：`2c35272226d40836f50ef1e4481cd6da3e9a4c672bb351123cb28801662ba1af`
- 字节数：538

```
{"description":"E02 origin: Vary lists two fields ('Vary: Accept, Accept-Encoding'). Accept is still a varying dimension, so the proxy must separate the representations and the classifier must see Vary: Accept as present.","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept, Accept-Encoding"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"Accept, Accept-Encoding"}},"scenario_id":"vary_multi"}
```

## fixtures/origin/vary_star.json

- SHA-256：`ca8b5fb4cf6834fb6bebc712293dbf33ee792a5c4a9859ded8c294feab94b5f5`
- 字节数：500

```
{"description":"E03 origin: Vary: * (RFC 9111 §4.1 — the stored response must never be reused). The proxy must not store the response and must report BYPASS; that BYPASS is compliant, not a variant-policy violation (ADR-004).","path":"/doc","representations":{"html":{"content_type":"text/html; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"*"},"markdown":{"content_type":"text/markdown; charset=utf-8","sentinel_mode":"correct","status":200,"vary":"*"}},"scenario_id":"vary_star"}
```

## fixtures/s0/C01.json

- SHA-256：`aa529e786ec822c45b32e2ca29c21773e4d9836f740670a7435b4f24120c9077`
- 字节数：568

```
{
  "scenario_id": "C01",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Correct Vary, respect_vary. All MISS, both warm orders correct.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "Correct Vary, respect_vary. All MISS, both warm orders correct."
}
```

## fixtures/s0/C02.json

- SHA-256：`9d69760ebef571ab117b36401d4c03506e1bbd25e4c14d5b4ca1b88ff32e68de`
- 字节数：614

```
{
  "scenario_id": "C02",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Same config as C01 (Markdown-first description); run always executes both warm orders.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "Same config as C01 (Markdown-first description); run always executes both warm orders."
}
```

## fixtures/s0/C03.json

- SHA-256：`73e59fda1ee6b199af2a735c4a90f5d34b67f2ba2450edd8bc0efc2312bceb04`
- 字节数：779

```
{
  "scenario_id": "C03",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Missing Vary, manual Accept key: healthy control for I-11; VARY_ACCEPT_ABSENT WARNING only.",
  "origin_scenario": "no_vary",
  "proxy_mode": "manual_accept_key",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 1
    },
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 2
    }
  ],
  "notes": "Missing Vary, manual Accept key: healthy control for I-11; VARY_ACCEPT_ABSENT WARNING only."
}
```

## fixtures/s0/C04.json

- SHA-256：`7fd6d5fffad6a18791ee4f06add2d7b4985954cca25eeb0a0c8a1dafd90ad521`
- 字节数：693

```
{
  "scenario_id": "C04",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Same config as C03 (Markdown-first description).",
  "origin_scenario": "no_vary",
  "proxy_mode": "manual_accept_key",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 1
    },
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 2
    }
  ],
  "notes": "Same config as C03 (Markdown-first description)."
}
```

## fixtures/s0/C05.json

- SHA-256：`42ae56de80b06bb5a7e6fcf3c0ab8ad4c332ed32c55431daae6ed702c457994e`
- 字节数：509

```
{
  "scenario_id": "C05",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "no-store, disabled proxy: all BYPASS.",
  "origin_scenario": "healthy",
  "proxy_mode": "disabled",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "no-store, disabled proxy: all BYPASS."
}
```

## fixtures/s0/C06.json

- SHA-256：`874c0204438fd1a15d317c9ca7f9bb19e9fdebec1b15a9d0c4d447e689beccde`
- 字节数：531

```
{
  "scenario_id": "C06",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Same config as C05 (Markdown-first description).",
  "origin_scenario": "healthy",
  "proxy_mode": "disabled",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "Same config as C05 (Markdown-first description)."
}
```

## fixtures/s0/C07.json

- SHA-256：`33c80f29a00dca4f776fdb69294fb4cd714b6ceda4ab068e559dd3fff4d205f3`
- 字节数：809

```
{
  "scenario_id": "C07",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Origin HTML returns 404.",
  "origin_scenario": "html_404",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "ORIGIN_NEGOTIATION_ERROR",
  "expected_first_error": 1,
  "expected_first_error_experiment_id": "ORIGIN_HTML",
  "expected_diagnostics": [
    {
      "code": "ORIGIN_NEGOTIATION_ERROR",
      "request_index": 1
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 3
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 5
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Origin HTML returns 404."
}
```

## fixtures/s0/C08.json

- SHA-256：`6c6c97e303f928dea98e769b314e4f09ffc75071a494ef0419618470279f7190`
- 字节数：825

```
{
  "scenario_id": "C08",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Origin Markdown returns 404.",
  "origin_scenario": "markdown_404",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "ORIGIN_NEGOTIATION_ERROR",
  "expected_first_error": 2,
  "expected_first_error_experiment_id": "ORIGIN_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "ORIGIN_NEGOTIATION_ERROR",
      "request_index": 2
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 4
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 7
    }
  ],
  "notes": "Origin Markdown returns 404."
}
```

## fixtures/s0/C09.json

- SHA-256：`acbdb2a1ad4bf5d095b19025ca953704dabd0e37a3a41ef53258aab76b75c3db`
- 字节数：848

```
{
  "scenario_id": "C09",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Origin HTML Content-Type text/plain.",
  "origin_scenario": "html_wrong_content_type",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "ORIGIN_NEGOTIATION_ERROR",
  "expected_first_error": 1,
  "expected_first_error_experiment_id": "ORIGIN_HTML",
  "expected_diagnostics": [
    {
      "code": "ORIGIN_NEGOTIATION_ERROR",
      "request_index": 1
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 3
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 5
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Origin HTML Content-Type text/plain."
}
```

## fixtures/s0/C10.json

- SHA-256：`ffb50739bc7ba306e96008ba022561be74d75682103181ffd442600154fc7cc0`
- 字节数：921

```
{
  "scenario_id": "C10",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Origin Markdown Sentinel missing.",
  "origin_scenario": "markdown_sentinel_missing",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "ORIGIN_NEGOTIATION_ERROR",
  "expected_first_error": 2,
  "expected_first_error_experiment_id": "ORIGIN_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "ORIGIN_NEGOTIATION_ERROR",
      "request_index": 2
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 2
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 4
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 7
    }
  ],
  "notes": "Origin Markdown Sentinel missing."
}
```

## fixtures/s0/C11.json

- SHA-256：`02bfb8fbda35135e16eac6853a44766f59e422dc129f19e377fb17225602c257`
- 字节数：1004

```
{
  "scenario_id": "C11",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Vary present, proxy forces URI-only: H->M bleed.",
  "origin_scenario": "healthy",
  "proxy_mode": "force_uri_only",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "REPRESENTATION_BLEED",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 8
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Vary present, proxy forces URI-only: H->M bleed."
}
```

## fixtures/s0/C12.json

- SHA-256：`3c52f9bcf2910046e2eac98879c9dbe8c8c9b58ed407233317de5a94c4cfbf01`
- 字节数：1080

```
{
  "scenario_id": "C12",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Same config as C11 (Markdown-first description); both warm orders bleed, first at 006.",
  "origin_scenario": "healthy",
  "proxy_mode": "force_uri_only",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "REPRESENTATION_BLEED",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 8
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Same config as C11 (Markdown-first description); both warm orders bleed, first at 006."
}
```

## fixtures/s0/C13.json

- SHA-256：`197f7150b02a49c6ebee94a35876b251a762cfd8e971a6f39e8611029400d572`
- 字节数：1150

```
{
  "scenario_id": "C13",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "No Vary, respect_vary keys URI-only: H->M bleed.",
  "origin_scenario": "no_vary",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "REPRESENTATION_BLEED",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 1
    },
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 2
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 8
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "No Vary, respect_vary keys URI-only: H->M bleed."
}
```

## fixtures/s0/C14.json

- SHA-256：`ccc6884c4915f10bd8d8c1a66850a252886ff72e76af275bf38caee8216283a8`
- 字节数：1150

```
{
  "scenario_id": "C14",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Same config as C13 (Markdown-first description).",
  "origin_scenario": "no_vary",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "REPRESENTATION_BLEED",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 1
    },
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 2
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 8
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Same config as C13 (Markdown-first description)."
}
```

## fixtures/s0/C15.json

- SHA-256：`15648d3a81283ee133cc63bb2321c1e9e5cfb4c52c4bd85cc7a1a4456b5338fa`
- 字节数：1128

```
{
  "scenario_id": "C15",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "No Vary, force_uri_only: H->M bleed.",
  "origin_scenario": "no_vary",
  "proxy_mode": "force_uri_only",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "REPRESENTATION_BLEED",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 1
    },
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 2
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 8
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "No Vary, force_uri_only: H->M bleed."
}
```

## fixtures/s0/C16.json

- SHA-256：`10ebc4f15c2b1104b3cdb8d0d7dd96e4614c36e1c2e77c0376cbbce200280ca2`
- 字节数：1152

```
{
  "scenario_id": "C16",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Same config as C15 (Markdown-first description).",
  "origin_scenario": "no_vary",
  "proxy_mode": "force_uri_only",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "REPRESENTATION_BLEED",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 1
    },
    {
      "code": "VARY_ACCEPT_ABSENT",
      "request_index": 2
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 6
    },
    {
      "code": "REPRESENTATION_BLEED",
      "request_index": 8
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 8
    },
    {
      "code": "SENTINEL_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "Same config as C15 (Markdown-first description)."
}
```

## fixtures/s0/C17.json

- SHA-256：`2f593dc7e4939de30d50cbe5a783b9979f673f8c92ea370b2bb6a3d62566af2d`
- 字节数：531

```
{
  "scenario_id": "C17",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "no-store, Vary missing, BYPASS: healthy control.",
  "origin_scenario": "no_vary",
  "proxy_mode": "disabled",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "no-store, Vary missing, BYPASS: healthy control."
}
```

## fixtures/s0/C18.json

- SHA-256：`cc56aa8743c8a769368626ba9e93b5a3fe5bc8726c6f7291d94ee1c5f159b538`
- 字节数：531

```
{
  "scenario_id": "C18",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "no-store, Vary present, BYPASS: healthy control.",
  "origin_scenario": "healthy",
  "proxy_mode": "disabled",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "PASS_OBSERVED",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [],
  "notes": "no-store, Vary present, BYPASS: healthy control."
}
```

## fixtures/s0/C19.json

- SHA-256：`1d6c4327b1e48841faf0f0eb0fc2b05547d9b12746b95d815e89389345bb9337`
- 字节数：1020

```
{
  "scenario_id": "C19",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "no-store contract but proxy stores (ignore_no_store).",
  "origin_scenario": "healthy",
  "proxy_mode": "ignore_no_store",
  "contract": {
    "mode": "no_store",
    "vary_accept": "not_required",
    "max_age_seconds": null
  },
  "injection": null,
  "expected_verdict": "CONTRACT_MISMATCH",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "CACHE_POLICY_MISMATCH",
      "request_index": 3
    },
    {
      "code": "CACHE_POLICY_MISMATCH",
      "request_index": 4
    },
    {
      "code": "CACHE_POLICY_MISMATCH",
      "request_index": 5
    },
    {
      "code": "CACHE_POLICY_MISMATCH",
      "request_index": 6
    },
    {
      "code": "CACHE_POLICY_MISMATCH",
      "request_index": 7
    },
    {
      "code": "CACHE_POLICY_MISMATCH",
      "request_index": 8
    }
  ],
  "notes": "no-store contract but proxy stores (ignore_no_store)."
}
```

## fixtures/s0/C20.json

- SHA-256：`f390ace8c263498f9ba8cd9059e863904e948d41ff840ce3e15a39f9b01ff387`
- 字节数：997

```
{
  "scenario_id": "C20",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Proxy hides Cache-Status headers: header leg missing.",
  "origin_scenario": "healthy",
  "proxy_mode": "opaque",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": null,
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 3
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 4
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 5
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 6
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 7
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 8
    }
  ],
  "notes": "Proxy hides Cache-Status headers: header leg missing."
}
```

## fixtures/s0/C21.json

- SHA-256：`40d3d4a5d3b9e8f1e76383c53e21e7310267eae199140652fadfea01feae7477`
- 字节数：1230

```
{
  "scenario_id": "C21",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Origin event journal unavailable at the adjudication boundary: classifier/Oracle receive an empty event list (checked, found nothing), never None.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "origin_events_unavailable"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 3,
  "expected_first_error_experiment_id": "HTML_COLD",
  "expected_diagnostics": [
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 3
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 4
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 5
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 6
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 7
    },
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": 8
    }
  ],
  "notes": "Origin event journal unavailable at the adjudication boundary: classifier/Oracle receive an empty event list (checked, found nothing), never None."
}
```

## fixtures/s0/C22.json

- SHA-256：`f9e138468903c64a8352726c56d20fe0a4a94b0ebb8437dc4b172f64e460d4f2`
- 字节数：940

```
{
  "scenario_id": "C22",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Harness proxy wrapper: 4th proxied GET (006 HM-2) returns a real HTTP response whose X-AcceptTwin-Cache-Status says HIT while the origin counter moved +1; header/behaviour conflict.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_lies_hit_on_warm_second"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": 6,
  "expected_first_error_experiment_id": "HTML_TO_MARKDOWN",
  "expected_diagnostics": [
    {
      "code": "CACHE_EVIDENCE_CONFLICT",
      "request_index": 6
    }
  ],
  "notes": "Harness proxy wrapper: 4th proxied GET (006 HM-2) returns a real HTTP response whose X-AcceptTwin-Cache-Status says HIT while the origin counter moved +1; header/behaviour conflict."
}
```

## fixtures/s0/C23.json

- SHA-256：`743ad6278b219442a99784f1145d69fa70a707ac662dcc0a79c589fa0067181b`
- 字节数：932

```
{
  "scenario_id": "C23",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Harness proxy wrapper: first cache reset reports success=false (store genuinely empty) so no cold-cache claim can be confirmed; run-level diagnostic, no single request is the first error.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "reset_reports_failure"
  },
  "expected_verdict": "INCONCLUSIVE",
  "expected_first_error": null,
  "expected_first_error_experiment_id": null,
  "expected_diagnostics": [
    {
      "code": "CACHE_STATE_UNKNOWN",
      "request_index": null
    }
  ],
  "notes": "Harness proxy wrapper: first cache reset reports success=false (store genuinely empty) so no cold-cache claim can be confirmed; run-level diagnostic, no single request is the first error."
}
```

## fixtures/s0/C24.json

- SHA-256：`32e1626dbfc89721e1a7cdced11e5bb061070e14b9fa89d9acff46c0ea0c514f`
- 字节数：1103

```
{
  "scenario_id": "C24",
  "spec": "PROJECT_BOOK.md §11.2",
  "description": "Harness proxy wrapper: proxied Markdown responses return Content-Type text/html (body unchanged); origin baselines stay correct, so this is a proxy contract violation, not an origin error.",
  "origin_scenario": "healthy",
  "proxy_mode": "respect_vary",
  "contract": {
    "mode": "variant_by_accept",
    "vary_accept": "advisory",
    "max_age_seconds": 60
  },
  "injection": {
    "kind": "proxy_rewrites_markdown_content_type"
  },
  "expected_verdict": "CONTRACT_MISMATCH",
  "expected_first_error": 4,
  "expected_first_error_experiment_id": "MARKDOWN_COLD",
  "expected_diagnostics": [
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 4
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 6
    },
    {
      "code": "CONTRACT_MISMATCH",
      "request_index": 7
    }
  ],
  "notes": "Harness proxy wrapper: proxied Markdown responses return Content-Type text/html (body unchanged); origin baselines stay correct, so this is a proxy contract violation, not an origin error."
}
```

## tests/fixtures/contracts/custom-bleed.json

- SHA-256：`9fb954061977dcf38e57b2a24bcc0876acea068a669d320031997d65eda7c972`
- 字节数：1243

```
{"cache_behavior":{"max_age_seconds":60,"mode":"variant_by_accept","vary_accept":"advisory"},"contract_id":"custom-bleed-001","limits":{"max_body_bytes":1048576,"request_timeout_seconds":5.0},"metadata":{"note":"P1-01 custom bleed contract (FIX-R1): a user-written contract, NOT a Golden replay. The contract itself is healthy (variant_by_accept); the bleed is produced by running it against a force_uri_only proxy, i.e. `accepttwin run --contract tests/fixtures/contracts/custom-bleed.json --proxy-mode force_uri_only`, which must yield REPRESENTATION_BLEED with first_error 6. Own loopback ports (18773 proxy / 18774 origin). See docs/USAGE.md."},"name":"Custom bleed site (synthetic origin + URI-only cache proxy)","origin_url":"http://127.0.0.1:18774/doc","representations":{"html":{"accept":"text/html","expected_content_type":"text/html; charset=utf-8","expected_status":200,"sentinel":"AT_HTML_SENTINEL_001"},"markdown":{"accept":"text/markdown","expected_content_type":"text/markdown; charset=utf-8","expected_status":200,"sentinel":"AT_MARKDOWN_SENTINEL_001"}},"request_headers":{"accept_encoding":"identity","accept_language":"en","user_agent":"AcceptTwin/1.0.0"},"schema":"accepttwin.contract/v1","url":"http://127.0.0.1:18773/doc"}
```

## tests/fixtures/contracts/custom-healthy.json

- SHA-256：`1ebb58499838efea8a32ce2438be2fcd72763a21d59a01950174db7f96f6379e`
- 字节数：1094

```
{"cache_behavior":{"max_age_seconds":60,"mode":"variant_by_accept","vary_accept":"advisory"},"contract_id":"custom-healthy-001","limits":{"max_body_bytes":1048576,"request_timeout_seconds":5.0},"metadata":{"note":"P1-01 custom healthy contract (FIX-R1): a user-written contract, NOT a Golden replay. Same shape as contracts/site.json but its own contract_id and its own loopback ports (18771 proxy / 18772 origin). Run with the default proxy mode (respect_vary) for PASS_OBSERVED. See docs/USAGE.md."},"name":"Custom healthy site (synthetic origin + controlled proxy)","origin_url":"http://127.0.0.1:18772/doc","representations":{"html":{"accept":"text/html","expected_content_type":"text/html; charset=utf-8","expected_status":200,"sentinel":"AT_HTML_SENTINEL_001"},"markdown":{"accept":"text/markdown","expected_content_type":"text/markdown; charset=utf-8","expected_status":200,"sentinel":"AT_MARKDOWN_SENTINEL_001"}},"request_headers":{"accept_encoding":"identity","accept_language":"en","user_agent":"AcceptTwin/1.0.0"},"schema":"accepttwin.contract/v1","url":"http://127.0.0.1:18771/doc"}
```

## tests/golden/test_all_48.py

- SHA-256：`5a3aa2ca51e94a250ac42add70eba4503bf7cd817f88007ecf40430ee5a51576`
- 字节数：5564

```
"""48-scenario integration tests (P032 T008): C01-C24 + E01-E24.

One combined golden + Oracle-parity test per scenario over the full
48, plus set-level invariants (§11.3, §12, §18 AC03):

* 48/48 Golden match frozen expectations;
* 48/48 Oracle parity, verdict + diagnostics + first error;
* S0 24 re-run here still pass (the S0 gate itself is
  ``tests/golden/test_s0.py`` + ``scripts/run_s0.py``);
* healthy 16 zero false positives; known failures 19 detected;
* insufficient-evidence 13 never misjudged as bleed/origin error;
* every scenario ran the full four experiments on real HTTP.

The deep per-suite checks live in ``test_s0.py`` (S0) and
``test_extended.py`` (E01–E24); this file proves the combined set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from s0_harness import (  # noqa: E402
    ALL_SCENARIO_IDS,
    EXTENDED_FIXTURE_DIR,
    EXTENDED_SCENARIO_IDS,
    FIXTURE_DIR,
    SCENARIO_IDS,
    check_parity,
    oracle_input_dict,
    run_oracle,
    run_scenario,
)

HEALTHY_48 = [
    "C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18",
    "E01", "E02", "E03", "E04", "E05", "E06", "E15", "E16",
]
KNOWN_FAILURES_48 = [
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
    "C15", "C16", "C19", "C24",
    "E09", "E10", "E11", "E13", "E14", "E23", "E24",
]
INSUFFICIENT_48 = [
    "C20", "C21", "C22", "C23",
    "E07", "E08", "E12", "E17", "E18", "E19", "E20", "E21", "E22",
]


def _suite_of(scenario_id: str):
    if scenario_id in SCENARIO_IDS:
        return FIXTURE_DIR, "s0"
    return EXTENDED_FIXTURE_DIR, "ext"


def _run(scenario_id: str, **kwargs):
    fixture_dir, prefix = _suite_of(scenario_id)
    return run_scenario(
        scenario_id,
        fixture_dir=fixture_dir,
        contract_prefix=prefix,
        **kwargs,
    )


@pytest.mark.parametrize("scenario_id", ALL_SCENARIO_IDS)
def test_all_48_golden_and_parity(scenario_id, tmp_path):
    """Each of the 48 scenarios: frozen expectation + Oracle parity."""
    outcome = _run(scenario_id, namespace_prefix=f"all48-{scenario_id}")
    fx = outcome.fixture
    assert outcome.production.verdict == fx["expected_verdict"], scenario_id
    assert outcome.production.first_error == fx["expected_first_error"], scenario_id
    assert (
        outcome.production.first_error_experiment_id
        == fx["expected_first_error_experiment_id"]
    ), scenario_id
    assert outcome.diagnostics_projection == fx["expected_diagnostics"], scenario_id
    assert len(outcome.run.observations) == 8, scenario_id
    assert outcome.duration_seconds < 1.0, scenario_id

    injection = fx.get("injection") or {}
    input_path = tmp_path / f"{scenario_id}-oracle-input.json"
    output_path = tmp_path / f"{scenario_id}-oracle.json"
    input_path.write_text(
        json.dumps(
            oracle_input_dict(
                outcome.contract,
                outcome.run,
                outcome.adj_origin_events,
                origin_events_available=(
                    injection.get("kind") != "origin_events_unavailable"
                ),
            ),
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    oracle_result = run_oracle(input_path, output_path)
    parity = check_parity(outcome, oracle_result)
    assert parity["parity"], f"{scenario_id}: " + "; ".join(parity["mismatches"])


def test_all_48_healthy_zero_false_positives():
    assert len(HEALTHY_48) == 16
    for sid in HEALTHY_48:
        outcome = _run(sid, namespace_prefix=f"all48-{sid}-healthy")
        assert outcome.production.verdict == "PASS_OBSERVED", sid
        assert outcome.production.critical_count == 0, sid


def test_all_48_known_failures_detected():
    assert len(KNOWN_FAILURES_48) == 19
    for sid in KNOWN_FAILURES_48:
        outcome = _run(sid, namespace_prefix=f"all48-{sid}-known")
        assert outcome.production.verdict == outcome.fixture["expected_verdict"], sid
        assert outcome.production.first_error is not None, sid


def test_all_48_insufficient_evidence_never_misjudged():
    assert len(INSUFFICIENT_48) == 13
    for sid in INSUFFICIENT_48:
        outcome = _run(sid, namespace_prefix=f"all48-{sid}-insufficient")
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        codes = [d.code for d in outcome.production.diagnostics]
        assert "REPRESENTATION_BLEED" not in codes, sid
        assert "ORIGIN_NEGOTIATION_ERROR" not in codes, sid


def test_all_48_verdict_distribution():
    # The 48 split is fixed by §11.2/§11.3: 16 PASS, 4 origin errors
    # in S0 + 3 in extended, 6 bleeds in S0 + 2 in extended, 2
    # contract mismatches in S0 + 2 in extended, 4 inconclusive in
    # S0 + 9 in extended. Recomputed live (one run per scenario is
    # already covered above; this test re-runs cheaply via the same
    # harness and pins the distribution, not individual verdicts).
    counts: dict[str, int] = {}
    for sid in ALL_SCENARIO_IDS:
        outcome = _run(sid, namespace_prefix=f"all48-{sid}-dist")
        counts[outcome.production.verdict] = (
            counts.get(outcome.production.verdict, 0) + 1
        )
    assert counts == {
        "PASS_OBSERVED": 16,
        "ORIGIN_NEGOTIATION_ERROR": 7,
        "REPRESENTATION_BLEED": 8,
        "CONTRACT_MISMATCH": 4,
        "INCONCLUSIVE": 13,
    }
    assert sum(counts.values()) == 48
```

## tests/golden/test_extended.py

- SHA-256：`d66eb38e690ac1fa14505ef2072d44611b33e0d9d6f33f888d935c6492397d81`
- 字节数：13891

```
"""Extended Golden tests (P032 T008): E01-E24, independent Oracle.

Every test makes real HTTP requests over loopback through
``scripts/s0_harness.py`` (generalised by T008 to load the extended
fixtures; the same harness ``scripts/run_all_48.py`` uses for the
48-scenario gate). Expected verdicts, diagnostics and first-error
locations come from the frozen fixtures in ``fixtures/extended/`` --
never from the implementation under test.

Coverage (PROJECT_BOOK §11.3):
* 24/24 Golden match frozen expectations;
* 24/24 Oracle parity, verdict + diagnostics + first error (§12);
* healthy scenarios zero false positives (§7, §11.3);
* known failures detected (§8, §11.3);
* Vary lowercase field name (E01), multi-field Vary (E02),
  Vary:* (E03), no-store controls (E05/E06/E15/E16);
* revalidation limits (E07/E08), origin negotiation faults
  (E09–E11), cache-evidence faults (E17–E20), oversize body (E21),
  redirect limits (E12/E22), proxy response faults (E23/E24);
* stable bleed reproduction 3/3 for E13 (§8.2, §11.3);
* canonical report hash deterministic on re-execution (§7.8, §10.4);
* single scenario < 1s (§10.5);
* insufficient evidence never misjudged (§8.4, §8.8, §9.4).
"""

from __future__ import annotations

import http.client
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from s0_harness import (  # noqa: E402
    EXTENDED_FIXTURE_DIR,
    EXTENDED_SCENARIO_IDS,
    check_parity,
    load_scenario,
    make_pair,
    oracle_input_dict,
    run_oracle,
    run_scenario,
)
from accepttwin.origin_server import SyntheticOrigin  # noqa: E402

HEALTHY = ["E01", "E02", "E03", "E04", "E05", "E06", "E15", "E16"]
KNOWN_FAILURES = ["E09", "E10", "E11", "E13", "E14", "E23", "E24"]
INSUFFICIENT = ["E07", "E08", "E12", "E17", "E18", "E19", "E20", "E21", "E22"]


def _run(scenario_id: str, **kwargs):
    return run_scenario(
        scenario_id,
        fixture_dir=EXTENDED_FIXTURE_DIR,
        contract_prefix="ext",
        **kwargs,
    )


def _oracle_for(outcome, tmp_path: Path) -> dict:
    """Run the independent Oracle on this outcome's adjudication input."""
    injection = outcome.fixture.get("injection") or {}
    input_path = tmp_path / f"{outcome.scenario_id}-oracle-input.json"
    output_path = tmp_path / f"{outcome.scenario_id}-oracle.json"
    input_path.write_text(
        json.dumps(
            oracle_input_dict(
                outcome.contract,
                outcome.run,
                outcome.adj_origin_events,
                origin_events_available=(
                    injection.get("kind") != "origin_events_unavailable"
                ),
            ),
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_oracle(input_path, output_path)


@pytest.mark.parametrize("scenario_id", EXTENDED_SCENARIO_IDS)
def test_golden_matches_frozen_expectation(scenario_id):
    outcome = _run(scenario_id, namespace_prefix=f"ext-{scenario_id}")
    fx = outcome.fixture
    assert outcome.production.verdict == fx["expected_verdict"]
    assert outcome.production.first_error == fx["expected_first_error"]
    assert (
        outcome.production.first_error_experiment_id
        == fx["expected_first_error_experiment_id"]
    )
    assert outcome.diagnostics_projection == fx["expected_diagnostics"]
    # Full four experiments, real requests, frozen order.
    assert len(outcome.run.observations) == 8
    assert [o.request_index for o in outcome.run.observations] == list(range(1, 9))
    assert [o.experiment_id for o in outcome.run.observations] == [
        "ORIGIN_HTML", "ORIGIN_MARKDOWN", "HTML_COLD", "MARKDOWN_COLD",
        "HTML_TO_MARKDOWN", "HTML_TO_MARKDOWN",
        "MARKDOWN_TO_HTML", "MARKDOWN_TO_HTML",
    ]
    assert len(outcome.run.reset_evidence) == 4
    assert len(outcome.run.step_log) == 25
    # No body text anywhere in the evidence (§7.12 I-12).
    evidence_text = json.dumps(outcome.run.as_dict())
    assert "AT_HTML_SENTINEL_001" not in evidence_text
    assert "AT_MARKDOWN_SENTINEL_001" not in evidence_text
    assert "<!DOCTYPE html>" not in evidence_text
    # Single scenario < 1s (§10.5).
    assert outcome.duration_seconds < 1.0


@pytest.mark.parametrize("scenario_id", EXTENDED_SCENARIO_IDS)
def test_oracle_parity(scenario_id, tmp_path):
    outcome = _run(scenario_id, namespace_prefix=f"ext-{scenario_id}")
    oracle_result = _oracle_for(outcome, tmp_path)
    parity = check_parity(outcome, oracle_result)
    assert parity["parity"], "; ".join(parity["mismatches"])
    # The Oracle input must not carry a production verdict (§12.2).
    raw_input = json.loads(
        (tmp_path / f"{scenario_id}-oracle-input.json").read_text(encoding="utf-8")
    )
    assert "verdict" not in raw_input
    assert "diagnostics" not in raw_input


def test_healthy_zero_false_positives():
    for sid in HEALTHY:
        outcome = _run(sid, namespace_prefix=f"ext-{sid}")
        assert outcome.production.verdict == "PASS_OBSERVED", sid
        assert outcome.production.critical_count == 0, sid


def test_known_failures_detected():
    for sid in KNOWN_FAILURES:
        outcome = _run(sid, namespace_prefix=f"ext-{sid}")
        assert outcome.production.verdict == outcome.fixture["expected_verdict"], sid
        assert outcome.production.first_error is not None, sid


def test_insufficient_evidence_never_misjudged():
    for sid in INSUFFICIENT:
        outcome = _run(sid, namespace_prefix=f"ext-{sid}")
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        codes = [d.code for d in outcome.production.diagnostics]
        assert "REPRESENTATION_BLEED" not in codes, sid
        assert "ORIGIN_NEGOTIATION_ERROR" not in codes, sid


def test_e01_vary_field_name_is_lowercase_on_the_wire():
    # The runner lowercases header names in evidence (HTTP field
    # names are case-insensitive), so the lowercase wire fact is
    # pinned here with a raw request, not from the evidence file.
    origin = SyntheticOrigin(port=0, scenario="vary_lowercase")
    origin.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", origin.port, timeout=5)
        try:
            conn.request("GET", "/doc", headers={"Accept": "text/html"})
            resp = conn.getresponse()
            resp.read()
            names = [name for name, _ in resp.getheaders()]
        finally:
            conn.close()
    finally:
        origin.stop()
    assert "vary" in names
    assert "Vary" not in names
    # ...while the end-to-end run still passes (E01 golden above).
    outcome = _run("E01", namespace_prefix="ext-E01-wire")
    assert outcome.production.verdict == "PASS_OBSERVED"


def test_e02_vary_multi_field_is_observed():
    outcome = _run("E02", namespace_prefix="ext-E02-vary")
    assert outcome.production.verdict == "PASS_OBSERVED"
    for raw in outcome.run.raw_observations[:2]:
        assert raw.response_headers.get("vary") == "Accept, Accept-Encoding"


def test_e03_vary_star_never_stores_and_bypasses():
    outcome = _run("E03", namespace_prefix="ext-E03-vary")
    assert outcome.production.verdict == "PASS_OBSERVED"
    assert outcome.production.diagnostics == ()
    for raw in outcome.run.raw_observations:
        assert raw.response_headers.get("vary") == "*"
    for raw in outcome.run.raw_observations[2:]:
        assert raw.verified_cache_state == "BYPASS"
        assert raw.cache_entry_count_after == 0
        assert raw.cache_entry_count_before == 0


def test_e07_e08_revalidation_limit_codes():
    for sid in ("E07", "E08"):
        outcome = _run(sid, namespace_prefix=f"ext-{sid}-limit")
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        limits = [
            d for d in outcome.production.diagnostics
            if d.code == "INCONCLUSIVE_LIMIT"
        ]
        assert len(limits) == 8, sid
        assert {d.evidence["limit_code"] for d in limits} == {
            "revalidation_required"
        }, sid
        directive = "max-age=0" if sid == "E07" else "no-cache"
        assert outcome.run.raw_observations[0].response_headers.get(
            "cache-control"
        ) == directive, sid


def test_e12_e22_redirect_limit_codes_and_targets():
    for sid, target in (
        ("E12", None),  # loopback origin URL (port varies per run)
        ("E22", "http://example.com/doc"),
    ):
        outcome = _run(sid, namespace_prefix=f"ext-{sid}-redirect")
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        limits = [
            d for d in outcome.production.diagnostics
            if d.code == "INCONCLUSIVE_LIMIT"
        ]
        assert len(limits) == 6, sid
        assert {d.evidence["limit_code"] for d in limits} == {"redirect"}, sid
        assert {d.request_index for d in limits} == {3, 4, 5, 6, 7, 8}, sid
        for raw in outcome.run.raw_observations[2:]:
            assert raw.response_status == 301, sid
            location = raw.response_headers.get("location")
            assert location is not None, sid
            if target is None:
                assert location.startswith("http://127.0.0.1:"), sid
                assert location.endswith("/doc"), sid
            else:
                assert location == target, sid
        # The redirect is never followed: the origin saw only the
        # two direct baselines.
        assert outcome.run.origin_events and all(
            ev.index <= 2 for ev in outcome.run.origin_events
        ), sid


def test_e20_miss_header_conflicts_with_counter():
    outcome = _run("E20", namespace_prefix="ext-E20-conflict")
    assert outcome.production.verdict == "INCONCLUSIVE"
    assert outcome.production.first_error == 6
    second = outcome.run.raw_observations[5]
    assert second.cache_status_header == "MISS"
    assert second.origin_counter_delta == 0
    assert second.verified_cache_state == "CACHE_STATE_UNKNOWN"
    # The replayed body is the genuine Markdown body: no Sentinel
    # or contract diagnostic may fire alongside the conflict.
    assert second.sentinel_match is True
    assert second.response_content_type == "text/markdown; charset=utf-8"


def test_e21_oversize_bodies_are_measured_not_guessed():
    outcome = _run("E21", namespace_prefix="ext-E21-size")
    assert outcome.production.verdict == "INCONCLUSIVE"
    for raw in outcome.run.raw_observations[2:]:
        assert raw.body_size > 1048576
        assert raw.sentinel_match is True
    for raw in outcome.run.raw_observations[:2]:
        assert raw.body_size <= 1048576


def test_e24_warm_sentinel_corruption_is_not_a_bleed():
    outcome = _run("E24", namespace_prefix="ext-E24-sentinel")
    assert outcome.production.verdict == "CONTRACT_MISMATCH"
    assert outcome.production.first_error == 6
    for raw in (
        outcome.run.raw_observations[5],
        outcome.run.raw_observations[7],
    ):
        assert raw.sentinel_match is False
        assert raw.verified_cache_state == "MISS"
    # Corrupted bodies differ from the first requests' bodies, so
    # the bleed chain (equal body hash) cannot fire.
    assert outcome.run.raw_observations[5].body_sha256 != (
        outcome.run.raw_observations[4].body_sha256
    )
    assert outcome.run.raw_observations[7].body_sha256 != (
        outcome.run.raw_observations[6].body_sha256
    )


def test_bleed_reproduces_3_of_3_with_dual_evidence():
    for attempt in range(1, 4):
        outcome = _run("E13", namespace_prefix=f"ext-E13-test-{attempt}")
        assert outcome.production.verdict == "REPRESENTATION_BLEED"
        assert outcome.production.first_error == 6
        bleed = [
            d for d in outcome.diagnostics_projection
            if d["code"] == "REPRESENTATION_BLEED"
        ]
        assert len(bleed) == 2  # both warm orders bleed
        second = outcome.run.raw_observations[5]
        first = outcome.run.raw_observations[4]
        assert second.cache_status_header == "HIT"
        assert second.origin_counter_delta == 0
        assert second.cache_entry_id == first.cache_entry_id
        assert second.body_sha256 == first.body_sha256


def test_canonical_hash_deterministic_on_reexecution():
    # ADR-003: three real re-runs, each on a FRESH pair with fresh
    # OS-assigned ports, must give one hash (§10.4).
    hashes = []
    for i in range(3):
        outcome = _run("E01", namespace_prefix=f"ext-E01-det-{i+1}")
        assert outcome.production.verdict == "PASS_OBSERVED"
        hashes.append(outcome.report_hash)
    assert len(set(hashes)) == 1
    # Supplementary same-pair check: re-running on one fixed pair
    # must give the same hash as the fresh-pair runs.
    same_pair_hashes = []
    with make_pair(
        "E01", EXTENDED_FIXTURE_DIR, "ext"
    ) as pair:
        for i in range(3):
            outcome = run_scenario(
                "E01",
                pair=pair,
                fixture_dir=EXTENDED_FIXTURE_DIR,
                contract_prefix="ext",
                namespace_prefix=f"ext-E01-det-pair-{i+1}",
            )
            assert outcome.production.verdict == "PASS_OBSERVED"
            same_pair_hashes.append(outcome.report_hash)
    assert len(set(same_pair_hashes)) == 1
    assert same_pair_hashes[0] == hashes[0]


def test_fixtures_cover_all_24_scenarios():
    assert list(EXTENDED_SCENARIO_IDS) == [f"E{i:02d}" for i in range(1, 25)]
    for sid in EXTENDED_SCENARIO_IDS:
        fx = load_scenario(sid, EXTENDED_FIXTURE_DIR)
        assert fx["expected_verdict"] in (
            "PASS_OBSERVED", "ORIGIN_NEGOTIATION_ERROR",
            "REPRESENTATION_BLEED", "CONTRACT_MISMATCH", "INCONCLUSIVE",
        )
        assert isinstance(fx["expected_diagnostics"], list)
        assert fx["spec"] == "PROJECT_BOOK.md §11.3"
```

## tests/golden/test_s0.py

- SHA-256：`d105efb285db58f995f0d4fa28097f0c79161710edbe899580139c42f7ad07f5`
- 字节数：10590

```
"""S0 Golden tests (P032 T007): C01-C24, independent Oracle, S0 gate.

Every test makes real HTTP requests over loopback through
``scripts/s0_harness.py`` (the same harness ``scripts/run_s0.py``
uses for the gate). Expected verdicts, diagnostics and first-error
locations come from the frozen fixtures in ``fixtures/s0/`` -- never
from the implementation under test.

Coverage (PROJECT_BOOK §13):
* 24/24 Golden match frozen expectations (§11.2);
* 24/24 Oracle parity, verdict + diagnostics + first error (§12);
* healthy scenarios zero false positives (§7, §11.2);
* known failures detected (§8, §11.2);
* both warm orders really executed, no mid-warm reset (§0.2, §6);
* independent cold requests with dual MISS/BYPASS proof (§5.4, §6);
* dual cache evidence, header + behaviour (§5.3);
* stable bleed reproduction 3/3 (§8.2, §11.2);
* missing-Vary healthy control (§7.11, §11.2);
* canonical report hash deterministic on re-execution (§7.8, §10.4)
  -- the full 100-run check lives in scripts/run_s0.py;
* single scenario < 1s (§10.5);
* insufficient evidence never misjudged (§8.4, §8.8, §9.4);
* first-error location (§6.3, §8);
* mandatory classify_run call convention (ADR-002 Decision 3).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from s0_harness import (  # noqa: E402
    ROOT,
    SCENARIO_IDS,
    check_parity,
    load_scenario,
    make_pair,
    oracle_input_dict,
    report_hash,
    run_oracle,
    run_scenario,
)

HEALTHY = ["C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18"]
KNOWN_FAILURES = [
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
    "C15", "C16", "C19", "C24",
]
INSUFFICIENT = ["C20", "C21", "C22", "C23"]


def _oracle_for(outcome, tmp_path: Path) -> dict:
    """Run the independent Oracle on this outcome's adjudication input."""
    injection = outcome.fixture.get("injection") or {}
    input_path = tmp_path / f"{outcome.scenario_id}-oracle-input.json"
    output_path = tmp_path / f"{outcome.scenario_id}-oracle.json"
    input_path.write_text(
        json.dumps(
            oracle_input_dict(
                outcome.contract,
                outcome.run,
                outcome.adj_origin_events,
                origin_events_available=(
                    injection.get("kind") != "origin_events_unavailable"
                ),
            ),
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_oracle(input_path, output_path)


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_golden_matches_frozen_expectation(scenario_id):
    outcome = run_scenario(scenario_id)
    fx = outcome.fixture
    assert outcome.production.verdict == fx["expected_verdict"]
    assert outcome.production.first_error == fx["expected_first_error"]
    assert (
        outcome.production.first_error_experiment_id
        == fx["expected_first_error_experiment_id"]
    )
    assert outcome.diagnostics_projection == fx["expected_diagnostics"]
    # Full four experiments, real requests, frozen order.
    assert len(outcome.run.observations) == 8
    assert [o.request_index for o in outcome.run.observations] == list(range(1, 9))
    assert [o.experiment_id for o in outcome.run.observations] == [
        "ORIGIN_HTML", "ORIGIN_MARKDOWN", "HTML_COLD", "MARKDOWN_COLD",
        "HTML_TO_MARKDOWN", "HTML_TO_MARKDOWN",
        "MARKDOWN_TO_HTML", "MARKDOWN_TO_HTML",
    ]
    assert len(outcome.run.reset_evidence) == 4
    assert len(outcome.run.step_log) == 25
    # No body text anywhere in the evidence (§7.12 I-12).
    evidence_text = json.dumps(outcome.run.as_dict())
    assert "AT_HTML_SENTINEL_001" not in evidence_text
    assert "AT_MARKDOWN_SENTINEL_001" not in evidence_text
    assert "<!DOCTYPE html>" not in evidence_text
    # Single scenario < 1s (§10.5).
    assert outcome.duration_seconds < 1.0


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_oracle_parity(scenario_id, tmp_path):
    outcome = run_scenario(scenario_id)
    oracle_result = _oracle_for(outcome, tmp_path)
    parity = check_parity(outcome, oracle_result)
    assert parity["parity"], "; ".join(parity["mismatches"])
    # The Oracle input must not carry a production verdict (§12.2).
    raw_input = json.loads(
        (tmp_path / f"{scenario_id}-oracle-input.json").read_text(encoding="utf-8")
    )
    assert "verdict" not in raw_input
    assert "diagnostics" not in raw_input


def test_healthy_zero_false_positives():
    for sid in HEALTHY:
        outcome = run_scenario(sid)
        assert outcome.production.verdict == "PASS_OBSERVED", sid
        assert outcome.production.critical_count == 0, sid


def test_known_failures_detected():
    for sid in KNOWN_FAILURES:
        outcome = run_scenario(sid)
        assert outcome.production.verdict == outcome.fixture["expected_verdict"], sid
        assert outcome.production.first_error is not None, sid


def test_both_warm_orders_real_and_no_mid_warm_reset():
    outcome = run_scenario("C11")
    names = [rec.name for rec in outcome.run.step_log]
    assert names[18:20] == ["HTMLWarmFirst", "MarkdownWarmSecond"]
    assert names[23:25] == ["MarkdownWarmFirst", "HTMLWarmSecond"]
    assert [rec.step for rec in outcome.run.step_log if rec.name == "ResetCache"] == [9, 13, 17, 22]
    # Both warm seconds are real requests with real origin evidence.
    assert outcome.run.observations[5].request_index == 6
    assert outcome.run.observations[7].request_index == 8


def test_cold_requests_have_dual_miss_bypass_proof():
    for sid in ("C01", "C03", "C05", "C17"):
        outcome = run_scenario(sid)
        for idx in (3, 4):
            raw = outcome.run.raw_observations[idx - 1]
            assert raw.verified_cache_state in ("MISS", "BYPASS"), (sid, idx)
            assert raw.cache_entry_count_before == 0, (sid, idx)
            assert raw.origin_counter_delta == 1, (sid, idx)
            assert raw.origin_event_present is True, (sid, idx)


def test_bleed_reproduces_3_of_3_with_dual_evidence():
    for attempt in range(1, 4):
        outcome = run_scenario("C11", namespace_prefix=f"s0-C11-test-{attempt}")
        assert outcome.production.verdict == "REPRESENTATION_BLEED"
        assert outcome.production.first_error == 6
        bleed = [
            d for d in outcome.diagnostics_projection
            if d["code"] == "REPRESENTATION_BLEED"
        ]
        assert len(bleed) == 2  # both warm orders bleed
        # Dual evidence on the bleed itself (§8.2): HIT header + no
        # origin hit + same entry as the first request.
        second = outcome.run.raw_observations[5]
        first = outcome.run.raw_observations[4]
        assert second.cache_status_header == "HIT"
        assert second.origin_counter_delta == 0
        assert second.cache_entry_id == first.cache_entry_id
        assert second.body_sha256 == first.body_sha256


def test_missing_vary_healthy_control():
    for sid in ("C03", "C04"):
        outcome = run_scenario(sid)
        assert outcome.production.verdict == "PASS_OBSERVED"
        codes = [d.code for d in outcome.production.diagnostics]
        assert codes == ["VARY_ACCEPT_ABSENT", "VARY_ACCEPT_ABSENT"]
        assert "REPRESENTATION_BLEED" not in codes


def test_insufficient_evidence_never_misjudged():
    for sid in INSUFFICIENT:
        outcome = run_scenario(sid)
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        codes = [d.code for d in outcome.production.diagnostics]
        assert "REPRESENTATION_BLEED" not in codes, sid
        assert "ORIGIN_NEGOTIATION_ERROR" not in codes, sid


def test_canonical_hash_deterministic_on_reexecution():
    # ADR-003: three real re-runs, each on a FRESH pair with fresh
    # OS-assigned ports, must give one hash (§10.4). The old form ran
    # all three on one fixed pair and passed by construction; a
    # port-dependent hash fails this test. The full 100-run check is
    # scripts/run_s0.py; this test proves re-execution (not
    # recomputation) is deterministic.
    hashes = []
    for i in range(3):
        outcome = run_scenario("C01", namespace_prefix=f"s0-C01-det-{i+1}")
        assert outcome.production.verdict == "PASS_OBSERVED"
        hashes.append(outcome.report_hash)
    assert len(set(hashes)) == 1
    # Supplementary same-pair check: re-running on one fixed pair
    # must give the same hash as the fresh-pair runs.
    same_pair_hashes = []
    with make_pair("C01") as pair:
        for i in range(3):
            outcome = run_scenario(
                "C01", pair=pair, namespace_prefix=f"s0-C01-det-pair-{i+1}"
            )
            assert outcome.production.verdict == "PASS_OBSERVED"
            same_pair_hashes.append(outcome.report_hash)
    assert len(set(same_pair_hashes)) == 1
    assert same_pair_hashes[0] == hashes[0]


def test_mandatory_call_convention():
    src = (ROOT / "scripts" / "s0_harness.py").read_text(encoding="utf-8")
    assert "raw_observations=run.raw_observations" in src
    # The real call site is a single line carrying both the contract
    # arguments and raw_observations; the MANDATORY_CALL_SNIPPET doc
    # constant above it is split over several lines and must not match.
    call_lines = [
        ln for ln in src.splitlines()
        if "classify_run(contract, run.observations" in ln
        and "raw_observations=run.raw_observations" in ln
    ]
    assert call_lines, "no classify_run call site found"
    for ln in call_lines:
        assert "None" not in ln, f"None passed at call site: {ln}"
        assert "run.reset_evidence" in ln
        assert "run.observations" in ln


def test_oracle_sources_do_not_reference_production():
    oracle_src = ""
    for path in sorted((ROOT / "oracle" / "src").glob("*.ts")):
        oracle_src += path.read_text(encoding="utf-8")
    for forbidden in ("classify_run", "production.json", ".py", "accepttwin.classifier"):
        assert forbidden not in oracle_src, forbidden


def test_fixtures_cover_all_24_scenarios():
    assert list(SCENARIO_IDS) == [f"C{i:02d}" for i in range(1, 25)]
    for sid in SCENARIO_IDS:
        fx = load_scenario(sid)
        assert fx["expected_verdict"] in (
            "PASS_OBSERVED", "ORIGIN_NEGOTIATION_ERROR",
            "REPRESENTATION_BLEED", "CONTRACT_MISMATCH", "INCONCLUSIVE",
        )
        assert isinstance(fx["expected_diagnostics"], list)
```

## tests/integration/test_cache_proxy.py

- SHA-256：`82daaadfa6dbed2ad9ec864382d61cda848fdd74e0c8d9d7b4069672d169a4a7`
- 字节数：31741

```
"""Integration tests for the controlled cache proxy (P032 T004).

Acceptance criteria (IMPLEMENTATION_PLAN T004):

1. MISS: header MISS + origin counter +1.
2. HIT: header HIT + origin counter 0.
3. BYPASS: header BYPASS + origin counter +1.
4. reset leaves entry_count == 0.
5. force_uri_only genuinely reproduces a representation bleed.
6. respect_vary separates representations when Vary: Accept exists.
7. manual_accept_key separates representations without Vary.
8. no-store responses are never stored.
9. Conflicting / incomplete evidence yields CACHE_STATE_UNKNOWN.

Every test makes real HTTP requests over localhost (``http.client``,
no proxy environment variables). The origin and the proxy bind
OS-assigned loopback ports (``port=0``) except for the one test that
pins the frozen default ports 18765/18766 from ``contracts/site.json``.
Dual evidence is verified end to end with
:func:`accepttwin.cache_evidence.verify_cache_state`, fed by the
response headers on the wire and by counter deltas measured from
:class:`accepttwin.origin_server.SyntheticOrigin` — never by a preset
answer.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from accepttwin.cache_evidence import (
    CACHE_STATE_UNKNOWN,
    BehaviorEvidence,
    HeaderEvidence,
    verify_cache_state,
)
from accepttwin.cache_proxy import (
    CacheProxyError,
    ControlledCacheProxy,
)
from accepttwin.contract import load_contract, parse_contract
from accepttwin.origin_server import (
    HTML_SENTINEL,
    MARKDOWN_SENTINEL,
    SyntheticOrigin,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

HTML_ACCEPT = "text/html"
MARKDOWN_ACCEPT = "text/markdown"


# ---------------------------------------------------------------------------
# HTTP helpers (real localhost requests)
# ---------------------------------------------------------------------------


def get(port: int, path: str = "/doc", accept: str = HTML_ACCEPT):
    """One real GET over loopback; returns (status, headers, body)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers={"Accept": accept})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        conn.close()


def request_with_method(port: int, method: str, path: str = "/doc"):
    """One real non-GET request; returns (status, headers, body)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, headers={"Accept": HTML_ACCEPT})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        conn.close()


def post_reset(port: int, namespace: str = "test"):
    """POST the proxy control endpoint; returns the parsed JSON body."""
    payload = json.dumps({"namespace": namespace}).encode("utf-8")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(
            "POST",
            "/__accepttwin/reset",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, json.loads(body.decode("utf-8"))
    finally:
        conn.close()


def get_snapshot(port: int):
    """GET the proxy control endpoint; returns the parsed JSON body."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/__accepttwin/snapshot")
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, json.loads(body.decode("utf-8"))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures: origin + proxy pairs
# ---------------------------------------------------------------------------


class Pair:
    """A running (origin, proxy) pair; use as a context manager."""

    def __init__(self, mode, scenario="healthy", contract=None):
        self.origin = SyntheticOrigin(port=0, scenario=scenario)
        self.origin.start()
        kwargs: dict = {"port": 0, "mode": mode}
        if contract is not None:
            kwargs["contract"] = contract
        else:
            kwargs["origin_url"] = self.origin.url
        self.proxy = ControlledCacheProxy(**kwargs)
        self.proxy.start()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.proxy.stop()
        self.origin.stop()
        return False


def no_store_contract(origin_url: str):
    """A valid no_store contract pointing at *origin_url* (§5.2 ex. B)."""
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["origin_url"] = origin_url
    data["cache_behavior"] = {
        "mode": "no_store",
        "vary_accept": "not_required",
        "max_age_seconds": None,
    }
    return parse_contract(data)


def observe(pair: Pair, accept: str):
    """One proxied request with before/after evidence measured live.

    Returns a dict with the response and the measured deltas; nothing
    here is preset — the counter and event log are read from the live
    origin, the snapshot from the live proxy.
    """
    before_counter = pair.origin.counter_snapshot().total_requests
    before_events = pair.origin.event_log()
    before_ids = {
        e.entry_id for e in pair.proxy.cache_snapshot().entries
    }
    before_count = pair.proxy.cache_snapshot().entry_count
    status, headers, body = get(pair.proxy.port, accept=accept)
    after_counter = pair.origin.counter_snapshot().total_requests
    after_snapshot = pair.proxy.cache_snapshot()
    after_events = pair.origin.event_log()
    new_events = after_events[len(before_events):]
    return {
        "status": status,
        "headers": headers,
        "body": body,
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "counter_delta": after_counter - before_counter,
        "entry_count_delta": after_snapshot.entry_count - before_count,
        "entry_ids_before": before_ids,
        "entry_ids_after": {e.entry_id for e in after_snapshot.entries},
        "snapshot_after": after_snapshot,
        "new_events": new_events,
        "origin_event_present": any(
            ev.accept == accept and ev.status == status for ev in new_events
        ),
    }


def verify_observation(obs, expected: str | None = None):
    """Run the dual-evidence verifier on a live observation."""
    headers = obs["headers"]
    header = HeaderEvidence(
        status=headers.get("x-accepttwin-cache-status"),
        cache_key_sha256=headers.get("x-accepttwin-cache-key"),
        entry_id=headers.get("x-accepttwin-entry-id"),
    )
    entry_id = header.entry_id
    stored = None
    if entry_id is not None:
        for entry in obs["snapshot_after"].entries:
            if entry.entry_id == entry_id:
                stored = entry
                break
    behavior = BehaviorEvidence(
        origin_counter_delta=obs["counter_delta"],
        origin_event_present=obs["origin_event_present"],
        entry_created=(
            entry_id is not None
            and entry_id not in obs["entry_ids_before"]
            and entry_id in obs["entry_ids_after"]
        ),
        entry_id_matches=stored is not None,
        body_hash_matches=(
            stored is not None and stored.body_sha256 == obs["body_sha256"]
        ),
        entry_count_delta=obs["entry_count_delta"],
    )
    return verify_cache_state(header, behavior, expected=expected)


# ---------------------------------------------------------------------------
# MISS / HIT / BYPASS dual evidence (§5.3 A–C)
# ---------------------------------------------------------------------------


def test_miss_dual_evidence():
    with Pair("respect_vary") as pair:
        evidence = pair.proxy.reset_cache("test-miss")
        assert evidence.success and evidence.entries_after == 0
        obs = observe(pair, HTML_ACCEPT)
        assert obs["status"] == 200
        assert obs["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert len(obs["headers"]["x-accepttwin-cache-key"]) == 64
        assert obs["headers"]["x-accepttwin-entry-id"].startswith("entry-")
        assert HTML_SENTINEL.encode() in obs["body"]
        assert obs["counter_delta"] == 1
        assert obs["origin_event_present"] is True
        assert obs["entry_count_delta"] == 1
        assert verify_observation(obs, expected="MISS").state == "MISS"


def test_hit_dual_evidence():
    with Pair("respect_vary") as pair:
        pair.proxy.reset_cache("test-hit")
        first = observe(pair, HTML_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        second = observe(pair, HTML_ACCEPT)
        assert second["status"] == 200
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["headers"]["x-accepttwin-cache-key"] == (
            first["headers"]["x-accepttwin-cache-key"]
        )
        assert second["headers"]["x-accepttwin-entry-id"] == (
            first["headers"]["x-accepttwin-entry-id"]
        )
        assert second["body"] == first["body"]
        assert second["counter_delta"] == 0
        assert second["entry_count_delta"] == 0
        assert verify_observation(second, expected="HIT").state == "HIT"


def test_bypass_dual_evidence_disabled_mode():
    with Pair("disabled") as pair:
        pair.proxy.reset_cache("test-bypass")
        for _ in range(2):
            obs = observe(pair, HTML_ACCEPT)
            assert obs["status"] == 200
            assert obs["headers"]["x-accepttwin-cache-status"] == "BYPASS"
            assert "x-accepttwin-entry-id" not in obs["headers"]
            assert HTML_SENTINEL.encode() in obs["body"]
            assert obs["counter_delta"] == 1
            assert obs["origin_event_present"] is True
            assert obs["entry_count_delta"] == 0
            assert pair.proxy.cache_snapshot().entry_count == 0
            assert verify_observation(obs, expected="BYPASS").state == "BYPASS"


def test_no_store_contract_bypass_both_representations():
    with Pair("respect_vary") as pair:
        contract = no_store_contract(pair.origin.url)
        pair.proxy.stop()
        pair.proxy = ControlledCacheProxy(
            port=0, mode="respect_vary", contract=contract
        )
        pair.proxy.start()
        pair.proxy.reset_cache("test-no-store-contract")
        for accept, sentinel in (
            (HTML_ACCEPT, HTML_SENTINEL),
            (MARKDOWN_ACCEPT, MARKDOWN_SENTINEL),
        ):
            obs = observe(pair, accept)
            assert obs["headers"]["x-accepttwin-cache-status"] == "BYPASS"
            assert sentinel.encode() in obs["body"]
            assert obs["counter_delta"] == 1
            assert verify_observation(obs, expected="BYPASS").state == "BYPASS"
        assert pair.proxy.cache_snapshot().entry_count == 0


# ---------------------------------------------------------------------------
# Reset (§5.4)
# ---------------------------------------------------------------------------


def test_reset_leaves_entry_count_zero_in_process_and_over_http():
    with Pair("respect_vary") as pair:
        observe(pair, HTML_ACCEPT)
        observe(pair, MARKDOWN_ACCEPT)
        assert pair.proxy.cache_snapshot().entry_count == 2
        evidence = pair.proxy.reset_cache("experiment-1")
        assert evidence.success is True
        assert evidence.entries_before == 2
        assert evidence.entries_after == 0
        assert evidence.entries_removed == 2
        assert pair.proxy.cache_snapshot().entry_count == 0
        # Reset again over real HTTP; the control endpoint must confirm
        # the same empty state.
        observe(pair, HTML_ACCEPT)
        assert pair.proxy.cache_snapshot().entry_count == 1
        status, payload = post_reset(pair.proxy.port, "experiment-2")
        assert status == 200
        assert payload["success"] is True
        assert payload["entries_after"] == 0
        status, payload = get_snapshot(pair.proxy.port)
        assert status == 200
        assert payload["entry_count"] == 0


def test_reset_on_empty_store_succeeds():
    with Pair("respect_vary") as pair:
        evidence = pair.proxy.reset_cache("cold")
        assert evidence.success is True
        assert evidence.entries_before == 0
        assert evidence.entries_removed == 0


def test_reset_requires_non_empty_namespace():
    with Pair("respect_vary") as pair:
        with pytest.raises(CacheProxyError):
            pair.proxy.reset_cache("")


# ---------------------------------------------------------------------------
# Bleed reproduction (§11.2 C11–C16) and healthy separation (C01–C04)
# ---------------------------------------------------------------------------


def test_force_uri_only_reproduces_bleed_html_first():
    with Pair("force_uri_only") as pair:
        pair.proxy.reset_cache("test-bleed-hm")
        first = observe(pair, HTML_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert HTML_SENTINEL.encode() in first["body"]
        second = observe(pair, MARKDOWN_ACCEPT)
        # The Markdown request reuses the HTML entry: same key, HIT,
        # origin untouched, HTML body served for a Markdown request.
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["headers"]["x-accepttwin-cache-key"] == (
            first["headers"]["x-accepttwin-cache-key"]
        )
        assert second["counter_delta"] == 0
        assert HTML_SENTINEL.encode() in second["body"]
        assert MARKDOWN_SENTINEL.encode() not in second["body"]
        assert verify_observation(second, expected="HIT").state == "HIT"


def test_force_uri_only_reproduces_bleed_markdown_first():
    with Pair("force_uri_only") as pair:
        pair.proxy.reset_cache("test-bleed-mh")
        first = observe(pair, MARKDOWN_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        second = observe(pair, HTML_ACCEPT)
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["counter_delta"] == 0
        assert MARKDOWN_SENTINEL.encode() in second["body"]
        assert HTML_SENTINEL.encode() not in second["body"]
        assert verify_observation(second, expected="HIT").state == "HIT"


def test_respect_vary_separates_with_vary_accept():
    with Pair("respect_vary", scenario="healthy") as pair:
        pair.proxy.reset_cache("test-vary")
        html = observe(pair, HTML_ACCEPT)
        markdown = observe(pair, MARKDOWN_ACCEPT)
        assert html["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert markdown["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert html["counter_delta"] == 1
        assert markdown["counter_delta"] == 1
        assert HTML_SENTINEL.encode() in html["body"]
        assert MARKDOWN_SENTINEL.encode() in markdown["body"]
        assert html["headers"]["x-accepttwin-cache-key"] != (
            markdown["headers"]["x-accepttwin-cache-key"]
        )
        assert html["headers"]["x-accepttwin-entry-id"] != (
            markdown["headers"]["x-accepttwin-entry-id"]
        )
        assert pair.proxy.cache_snapshot().entry_count == 2
        assert verify_observation(html, expected="MISS").state == "MISS"
        assert verify_observation(markdown, expected="MISS").state == "MISS"


def test_respect_vary_without_vary_bleeds():
    # §11.2 C13: no Vary + respect_vary keys on the URI only, so the
    # second representation HITs the first entry.
    with Pair("respect_vary", scenario="no_vary") as pair:
        pair.proxy.reset_cache("test-no-vary")
        first = observe(pair, HTML_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        second = observe(pair, MARKDOWN_ACCEPT)
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["counter_delta"] == 0
        assert HTML_SENTINEL.encode() in second["body"]
        assert verify_observation(second, expected="HIT").state == "HIT"


def test_manual_accept_key_separates_without_vary():
    # §11.2 C03/C04: missing Vary alone is not a fault when the cache
    # still separates by Accept.
    with Pair("manual_accept_key", scenario="no_vary") as pair:
        pair.proxy.reset_cache("test-manual")
        html = observe(pair, HTML_ACCEPT)
        markdown = observe(pair, MARKDOWN_ACCEPT)
        assert html["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert markdown["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert HTML_SENTINEL.encode() in html["body"]
        assert MARKDOWN_SENTINEL.encode() in markdown["body"]
        assert pair.proxy.cache_snapshot().entry_count == 2
        assert verify_observation(html, expected="MISS").state == "MISS"
        assert verify_observation(markdown, expected="MISS").state == "MISS"


# ---------------------------------------------------------------------------
# no-store from the origin, ignore_no_store, opaque (§5.2, §10.3, §11.2)
# ---------------------------------------------------------------------------


class _StubOriginHandler(BaseHTTPRequestHandler):
    """Test-only origin that can emit Cache-Control / Vary the synthetic
    origin cannot (no-store, Vary: *). Records request headers so the
    test can prove the proxy forwards only the fixed header set."""

    protocol_version = "HTTP/1.1"
    server_version = "StubOrigin/1.0.0"

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        server = self.server  # type: ignore[attr-defined]
        server.requests.append(dict(self.headers.items()))
        accept = self.headers.get("Accept", "")
        if "text/markdown" in accept:
            body = f"# stub\n\n{MARKDOWN_SENTINEL}\n".encode()
            content_type = "text/markdown; charset=utf-8"
        else:
            body = f"<html><body>{HTML_SENTINEL}</body></html>\n".encode()
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if server.vary is not None:
            self.send_header("Vary", server.vary)
        if server.cache_control is not None:
            self.send_header("Cache-Control", server.cache_control)
        self.end_headers()
        self.wfile.write(body)


class _StubOrigin:
    """Minimal counting origin for header-level fault injection."""

    def __init__(self, *, vary="Accept", cache_control=None):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _StubOriginHandler)
        self._server.daemon_threads = True
        self._server.vary = vary  # type: ignore[attr-defined]
        self._server.cache_control = cache_control  # type: ignore[attr-defined]
        self._server.requests = []  # type: ignore[attr-defined]
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05},
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/doc"

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def request_count(self) -> int:
        return len(self._server.requests)  # type: ignore[attr-defined]

    @property
    def seen_headers(self) -> list[dict]:
        return list(self._server.requests)  # type: ignore[attr-defined]

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)
        return False


def test_origin_no_store_response_is_never_stored():
    with _StubOrigin(cache_control="no-store") as stub:
        proxy = ControlledCacheProxy(
            origin_url=stub.url, port=0, mode="respect_vary"
        )
        proxy.start()
        try:
            proxy.reset_cache("test-origin-no-store")
            for _ in range(2):
                before = stub.request_count
                status, headers, body = get(proxy.port, accept=HTML_ACCEPT)
                assert status == 200
                assert headers["x-accepttwin-cache-status"] == "BYPASS"
                assert stub.request_count == before + 1
            assert proxy.cache_snapshot().entry_count == 0
        finally:
            proxy.stop()


def test_ignore_no_store_stores_despite_contract():
    with Pair("respect_vary") as pair:
        contract = no_store_contract(pair.origin.url)
        pair.proxy.stop()
        pair.proxy = ControlledCacheProxy(
            port=0, mode="ignore_no_store", contract=contract
        )
        pair.proxy.start()
        pair.proxy.reset_cache("test-ignore-no-store")
        first = observe(pair, HTML_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        second = observe(pair, HTML_ACCEPT)
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["counter_delta"] == 0
        assert pair.proxy.cache_snapshot().entry_count == 1


def test_vary_star_is_never_reused():
    # §11.3 E03 groundwork: Vary: * entries must not be reused.
    # A Vary: * response is fetched but never stored, so it is
    # reported BYPASS, not MISS (P2-1): MISS requires an entry to be
    # created (§5.3 A), while the observed behaviour leg (origin +1,
    # entry count unchanged) is exactly the BYPASS leg (§5.3 C).
    with _StubOrigin(vary="*") as stub:
        proxy = ControlledCacheProxy(
            origin_url=stub.url, port=0, mode="respect_vary"
        )
        proxy.start()
        try:
            proxy.reset_cache("test-vary-star")
            for _ in range(2):
                before_count = stub.request_count
                before_entries = proxy.cache_snapshot().entry_count
                status, headers, _body = get(proxy.port, accept=HTML_ACCEPT)
                assert status == 200
                assert headers["x-accepttwin-cache-status"] == "BYPASS"
                assert "x-accepttwin-entry-id" not in headers
                # The stub origin recorded the request: the origin was
                # reached and nothing was reused.
                origin_hit = stub.request_count == before_count + 1
                assert origin_hit
                assert proxy.cache_snapshot().entry_count == 0
                result = verify_cache_state(
                    HeaderEvidence(
                        status=headers.get("x-accepttwin-cache-status"),
                        cache_key_sha256=headers.get(
                            "x-accepttwin-cache-key"
                        ),
                        entry_id=headers.get("x-accepttwin-entry-id"),
                    ),
                    BehaviorEvidence(
                        origin_counter_delta=(
                            stub.request_count - before_count
                        ),
                        origin_event_present=origin_hit,
                        entry_count_delta=(
                            proxy.cache_snapshot().entry_count
                            - before_entries
                        ),
                    ),
                    expected="BYPASS",
                )
                assert result.state == "BYPASS"
            assert proxy.cache_snapshot().entry_count == 0
        finally:
            proxy.stop()


def test_ignore_no_store_stores_origin_no_store_response():
    # P2-2: ignore_no_store + origin Cache-Control: no-store — the
    # origin response is stored despite no-store, so the first
    # request is a MISS, the second identical request is a HIT, the
    # origin is hit only once, and exactly one entry exists.
    with _StubOrigin(cache_control="no-store") as stub:
        proxy = ControlledCacheProxy(
            origin_url=stub.url, port=0, mode="ignore_no_store"
        )
        proxy.start()
        try:
            proxy.reset_cache("test-ignore-no-store-origin")
            before = stub.request_count
            status, headers, _body = get(proxy.port, accept=HTML_ACCEPT)
            assert status == 200
            assert headers["x-accepttwin-cache-status"] == "MISS"
            assert stub.request_count == before + 1
            before = stub.request_count
            status, headers, _body = get(proxy.port, accept=HTML_ACCEPT)
            assert status == 200
            assert headers["x-accepttwin-cache-status"] == "HIT"
            assert stub.request_count == before
            assert proxy.cache_snapshot().entry_count == 1
        finally:
            proxy.stop()


def test_opaque_hides_header_leg_so_state_is_unknown():
    # §11.2 C20: the proxy still caches (second identical request
    # does not reach the origin) but hides the header leg, so the
    # dual-evidence verifier must answer UNKNOWN, not guess HIT.
    with Pair("opaque") as pair:
        pair.proxy.reset_cache("test-opaque")
        first = observe(pair, HTML_ACCEPT)
        assert "x-accepttwin-cache-status" not in first["headers"]
        assert "x-accepttwin-cache-key" not in first["headers"]
        assert "x-accepttwin-entry-id" not in first["headers"]
        assert first["counter_delta"] == 1
        result = verify_observation(first)
        assert result.state == CACHE_STATE_UNKNOWN
        assert any("cache-status" in r for r in result.reasons)
        second = observe(pair, HTML_ACCEPT)
        assert "x-accepttwin-cache-status" not in second["headers"]
        assert second["counter_delta"] == 0  # stored, despite hidden headers
        assert second["body"] == first["body"]
        assert verify_observation(second).state == CACHE_STATE_UNKNOWN


def test_proxy_forwards_only_the_fixed_header_set():
    with _StubOrigin() as stub:
        proxy = ControlledCacheProxy(
            origin_url=stub.url, port=0, mode="respect_vary"
        )
        proxy.start()
        try:
            get(proxy.port, accept=HTML_ACCEPT)
            assert len(stub.seen_headers) == 1
            seen = {k.lower(): v for k, v in stub.seen_headers[0].items()}
            assert seen["accept"] == HTML_ACCEPT
            assert seen["accept-encoding"] == "identity"
            assert seen["user-agent"] == "AcceptTwin/1.0.0"
            assert seen["accept-language"] == "en"
            assert "cookie" not in seen
            assert "authorization" not in seen
        finally:
            proxy.stop()


# ---------------------------------------------------------------------------
# Failure paths still produce complete dual evidence (T001 §7 lesson)
# ---------------------------------------------------------------------------


def test_origin_error_response_still_carries_miss_evidence():
    # C07: the origin answers 404 for HTML. The proxy forwards the
    # error *and* its MISS headers, so the failure path yields complete
    # dual evidence instead of short-circuiting like Hurl (T001 §4).
    with Pair("respect_vary", scenario="html_404") as pair:
        pair.proxy.reset_cache("test-origin-error")
        first = observe(pair, HTML_ACCEPT)
        assert first["status"] == 404
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert first["headers"]["x-accepttwin-entry-id"].startswith("entry-")
        assert first["counter_delta"] == 1
        assert verify_observation(first, expected="MISS").state == "MISS"
        second = observe(pair, HTML_ACCEPT)
        assert second["status"] == 404
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["counter_delta"] == 0
        assert verify_observation(second, expected="HIT").state == "HIT"


# ---------------------------------------------------------------------------
# Determinism, snapshots, methods, configuration
# ---------------------------------------------------------------------------


def test_cache_key_and_entry_id_are_deterministic_across_reset():
    with Pair("respect_vary") as pair:
        pair.proxy.reset_cache("test-determinism")
        first = observe(pair, HTML_ACCEPT)
        key1 = first["headers"]["x-accepttwin-cache-key"]
        entry1 = first["headers"]["x-accepttwin-entry-id"]
        pair.proxy.reset_cache("test-determinism-2")
        second = observe(pair, HTML_ACCEPT)
        assert second["headers"]["x-accepttwin-cache-key"] == key1
        assert second["headers"]["x-accepttwin-entry-id"] == entry1


def test_snapshot_contains_hashes_not_bodies():
    with Pair("respect_vary") as pair:
        pair.proxy.reset_cache("test-snapshot")
        observe(pair, HTML_ACCEPT)
        status, payload = get_snapshot(pair.proxy.port)
        assert status == 200
        assert payload["entry_count"] == 1
        entry = payload["entries"][0]
        assert "body" not in entry
        assert HTML_SENTINEL not in json.dumps(payload)
        _s, _h, body = get(pair.proxy.port, accept=HTML_ACCEPT)
        assert entry["body_sha256"] == hashlib.sha256(body).hexdigest()


def test_non_get_is_rejected_without_origin_contact_or_cache_headers():
    with Pair("respect_vary") as pair:
        before = pair.origin.counter_snapshot().total_requests
        status, headers, _body = request_with_method(pair.proxy.port, "POST")
        assert status == 405
        assert "x-accepttwin-cache-status" not in headers
        assert pair.origin.counter_snapshot().total_requests == before


def test_control_endpoints_do_not_touch_origin_counter():
    with Pair("respect_vary") as pair:
        before = pair.origin.counter_snapshot().total_requests
        status, _payload = get_snapshot(pair.proxy.port)
        assert status == 200
        status, payload = post_reset(pair.proxy.port, "control-check")
        assert status == 200
        assert payload["success"] is True
        assert pair.origin.counter_snapshot().total_requests == before


def test_default_ports_from_site_contract():
    contract = load_contract(CONTRACT_PATH)
    origin = SyntheticOrigin(port=18766, scenario="healthy")
    origin.start()
    proxy = ControlledCacheProxy(port=18765, mode="respect_vary", contract=contract)
    proxy.start()
    try:
        assert proxy.url == "http://127.0.0.1:18765/doc"
        proxy.reset_cache("test-default-ports")
        status, headers, body = get(18765, accept=HTML_ACCEPT)
        assert status == 200
        assert headers["x-accepttwin-cache-status"] == "MISS"
        assert HTML_SENTINEL.encode() in body
    finally:
        proxy.stop()
        origin.stop()


def test_unknown_mode_rejected():
    with pytest.raises(CacheProxyError):
        ControlledCacheProxy(origin_url="http://127.0.0.1:18766/doc", mode="cdn")


def test_non_loopback_origin_rejected():
    with pytest.raises(CacheProxyError):
        ControlledCacheProxy(origin_url="http://93.184.216.34/doc")


def test_non_loopback_proxy_host_rejected():
    with pytest.raises(CacheProxyError):
        ControlledCacheProxy(
            origin_url="http://127.0.0.1:18766/doc", host="0.0.0.0"
        )


def test_explicit_origin_url_disagreeing_with_contract_rejected():
    contract = load_contract(CONTRACT_PATH)
    with pytest.raises(CacheProxyError):
        ControlledCacheProxy(
            origin_url="http://127.0.0.1:19999/doc", contract=contract
        )
```

## tests/integration/test_cli_commands.py

- SHA-256：`773b05000efde80e4853b5e6efbb8dbd978bdd901757ba15cb1ee46ceb786231`
- 字节数：23508

```
"""CLI tests (P032 P1-01 FIX-R1): ``run`` / ``demo`` / ``verify --report`` /
``report preview|export|delete`` / ``clean`` / ``contract delete``.

Every positive test runs the real entry point
(``python -m accepttwin``) with real HTTP experiments and the real
independent Oracle — no Golden replay, no mocked runner. The two
custom contracts under ``tests/fixtures/contracts/`` are user-written
contracts (own contract_ids, own loopback ports), not Golden
fixtures: the healthy one must yield PASS_OBSERVED and the bleed one
(with ``--proxy-mode force_uri_only``) must yield
REPRESENTATION_BLEED with first_error 6.

Negative tests assert the exit-code contract (0 = command succeeded,
1 = gate/verification failure, 2 = bad input / refused deletion)
and that refused deletions never delete the victim file.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HEALTHY_CONTRACT = ROOT / "tests" / "fixtures" / "contracts" / "custom-healthy.json"
BLEED_CONTRACT = ROOT / "tests" / "fixtures" / "contracts" / "custom-bleed.json"
RUNS_DIR = ROOT / "output" / "runs"


def _run_cli(*argv: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "accepttwin", *argv],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=timeout,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tracked_run_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id


@pytest.fixture(scope="module")
def healthy_run() -> dict:
    """One live healthy custom-contract run, shared by read-only tests."""
    run_id = "cli-test-healthy"
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--run-id", run_id
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out_dir = _tracked_run_dir(run_id)
    report = _read_json(out_dir / "report.json")
    yield {"run_id": run_id, "out_dir": out_dir, "report": report, "proc": proc}
    # Leave the evidence in place: it is under output/ (git-ignored)
    # and documents the run. Tests that need a fresh copy duplicate it.


@pytest.fixture(scope="module")
def bleed_run() -> dict:
    """One live bleed custom-contract run, shared by read-only tests."""
    run_id = "cli-test-bleed"
    proc = _run_cli(
        "run",
        "--contract",
        str(BLEED_CONTRACT),
        "--proxy-mode",
        "force_uri_only",
        "--run-id",
        run_id,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out_dir = _tracked_run_dir(run_id)
    report = _read_json(out_dir / "report.json")
    yield {"run_id": run_id, "out_dir": out_dir, "report": report, "proc": proc}


# ---------------------------------------------------------------------------
# run --contract: healthy custom contract
# ---------------------------------------------------------------------------


def test_run_healthy_custom_contract(healthy_run):
    proc = healthy_run["proc"]
    assert "RUN_STATUS: COMPLETE" in proc.stdout
    assert "verdict=PASS_OBSERVED" in proc.stdout
    assert "oracle_parity=True" in proc.stdout
    report = healthy_run["report"]
    assert report["schema"] == "accepttwin.report/v1"
    assert report["verdict"] == "PASS_OBSERVED"
    assert report["first_error"] is None
    assert report["oracle_parity"] is True
    assert report["final"] is True
    assert report["scenario_id"] == "C01"
    assert report["input"]["contract_id"] == "custom-healthy-001"
    assert len(report["observations"]) == 8
    assert [o["request_index"] for o in report["observations"]] == list(range(1, 9))
    assert [o["cache_status"] for o in report["observations"][2:]] == ["MISS"] * 6
    # Sibling evidence files all exist.
    for name in (
        "contract.json",
        "raw-observations.json",
        "production.json",
        "oracle-input.json",
        "oracle.json",
        "run-summary.json",
    ):
        assert (healthy_run["out_dir"] / name).is_file(), name
    summary = _read_json(healthy_run["out_dir"] / "run-summary.json")
    assert summary["contract_id"] == "custom-healthy-001"
    assert summary["proxy_mode"] == "respect_vary"
    assert summary["ok"] is True


def test_run_report_hash_recomputes(healthy_run):
    from accepttwin.report_builder import compute_report_hash

    report = healthy_run["report"]
    assert compute_report_hash(report) == report["report_hash"]


def test_run_report_is_schema_valid(healthy_run):
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "tests" / "unit"))
    from independent_schema_validator import validate

    assert validate(healthy_run["report"]) == []


def test_run_oracle_agrees_with_production(healthy_run):
    out_dir = healthy_run["out_dir"]
    production = _read_json(out_dir / "production.json")
    oracle = _read_json(out_dir / "oracle.json")
    report = healthy_run["report"]
    assert oracle["verdict"] == production["verdict"] == report["verdict"]
    assert oracle["first_error"] == production["first_error"]
    assert oracle["verified_cache_states"] == production["confirmed_cache_states"]
    assert report["oracle"]["verdict"] == oracle["verdict"]


def test_run_bleed_custom_contract(bleed_run):
    proc = bleed_run["proc"]
    assert "verdict=REPRESENTATION_BLEED" in proc.stdout
    report = bleed_run["report"]
    assert report["verdict"] == "REPRESENTATION_BLEED"
    assert report["first_error"] == 6
    assert report["first_error_experiment_id"] == "HTML_TO_MARKDOWN"
    assert report["oracle_parity"] is True
    assert report["final"] is True
    assert report["scenario_id"] == "C11"
    states = {o["request_index"]: o["cache_status"] for o in report["observations"]}
    assert states[6] == "HIT" and states[8] == "HIT"
    oracle = _read_json(bleed_run["out_dir"] / "oracle.json")
    assert oracle["verdict"] == "REPRESENTATION_BLEED"
    assert oracle["verified_cache_states"] == _read_json(
        bleed_run["out_dir"] / "production.json"
    )["confirmed_cache_states"]


def test_run_with_output_path(tmp_path):
    out = tmp_path / "my-report.json"
    proc = _run_cli(
        "run",
        "--contract",
        str(HEALTHY_CONTRACT),
        "--run-id",
        "cli-test-output",
        "--output",
        str(out),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.is_file()
    assert (tmp_path / "run-summary.json").is_file()
    assert (tmp_path / "oracle.json").is_file()
    assert _read_json(out)["verdict"] == "PASS_OBSERVED"


def test_run_explicit_scenario_id_for_unmapped_config():
    # no_vary + opaque is not in the S0 configuration table, so it
    # needs an explicit label — and then it runs for real.
    proc = _run_cli(
        "run",
        "--contract",
        str(BLEED_CONTRACT),
        "--scenario",
        "no_vary",
        "--proxy-mode",
        "opaque",
        "--scenario-id",
        "E17",
        "--run-id",
        "cli-test-unmapped",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = _read_json(_tracked_run_dir("cli-test-unmapped") / "report.json")
    assert report["scenario_id"] == "E17"
    assert report["oracle_parity"] is True
    assert report["final"] is True


# ---------------------------------------------------------------------------
# run --contract: negative tests
# ---------------------------------------------------------------------------


def test_run_invalid_contract(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "accepttwin.contract/v1", "contract_id": 1}', encoding="utf-8")
    proc = _run_cli("run", "--contract", str(bad), "--run-id", "cli-test-bad")
    assert proc.returncode == 2
    assert not _tracked_run_dir("cli-test-bad").exists()


def test_run_missing_contract_file():
    proc = _run_cli(
        "run", "--contract", "tests/fixtures/contracts/does-not-exist.json"
    )
    assert proc.returncode == 2
    assert "not found" in proc.stderr


def test_run_non_loopback_contract(tmp_path):
    data = _read_json(HEALTHY_CONTRACT)
    data["url"] = "http://8.8.8.8:18771/doc"
    data["origin_url"] = "http://8.8.8.8:18772/doc"
    path = tmp_path / "public.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    proc = _run_cli("run", "--contract", str(path))
    assert proc.returncode == 2


def test_run_unknown_scenario():
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--scenario", "no-such-scenario"
    )
    assert proc.returncode == 2


def test_run_unknown_proxy_mode():
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--proxy-mode", "bogus"
    )
    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


def test_run_invalid_scenario_id():
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--scenario-id", "CUSTOM"
    )
    assert proc.returncode == 2


def test_run_unmapped_config_without_scenario_id():
    proc = _run_cli(
        "run",
        "--contract",
        str(BLEED_CONTRACT),
        "--scenario",
        "no_vary",
        "--proxy-mode",
        "opaque",
    )
    assert proc.returncode == 2
    assert "--scenario-id" in proc.stderr


def test_run_bad_run_id():
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--run-id", "../escape"
    )
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------


def test_demo_passes_with_both_verdicts_and_html():
    proc = _run_cli("demo")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DEMO_STATUS: PASS" in proc.stdout
    healthy = _read_json(RUNS_DIR / "demo-healthy" / "report.json")
    bleed = _read_json(RUNS_DIR / "demo-bleed" / "report.json")
    assert healthy["verdict"] == "PASS_OBSERVED"
    assert healthy["oracle_parity"] is True and healthy["final"] is True
    assert bleed["verdict"] == "REPRESENTATION_BLEED"
    assert bleed["first_error"] == 6
    assert bleed["oracle_parity"] is True and bleed["final"] is True
    for run_id in ("demo-healthy", "demo-bleed"):
        html = RUNS_DIR / run_id / "report.html"
        assert html.is_file()
        text = html.read_text(encoding="utf-8")
        assert _read_json(RUNS_DIR / run_id / "report.json")["report_hash"] in text
        assert "AT_HTML_SENTINEL_001" not in text
        assert "AT_MARKDOWN_SENTINEL_001" not in text


# ---------------------------------------------------------------------------
# verify --report
# ---------------------------------------------------------------------------


def test_verify_report_healthy(healthy_run):
    proc = _run_cli("verify", "--report", str(healthy_run["out_dir"] / "report.json"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFY_REPORT: C01" in proc.stdout
    assert "verdict=PASS_OBSERVED" in proc.stdout
    assert "schema=OK hash=OK" in proc.stdout


def test_verify_report_bleed_is_valid(bleed_run):
    proc = _run_cli(
        "verify", "--report", str(bleed_run["out_dir"] / "report.json")
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "verdict=REPRESENTATION_BLEED" in proc.stdout


def test_verify_report_with_matching_contract(healthy_run):
    proc = _run_cli(
        "verify",
        "--report",
        str(healthy_run["out_dir"] / "report.json"),
        "--contract",
        str(HEALTHY_CONTRACT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "contract_sha256=OK" in proc.stdout


def test_verify_report_with_wrong_contract(healthy_run):
    proc = _run_cli(
        "verify",
        "--report",
        str(healthy_run["out_dir"] / "report.json"),
        "--contract",
        str(BLEED_CONTRACT),
    )
    assert proc.returncode == 1
    assert "does not match" in proc.stderr


def test_verify_report_tampered_hash(healthy_run, tmp_path):
    report = dict(healthy_run["report"])
    report["verdict"] = "CONTRACT_MISMATCH"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(report), encoding="utf-8")
    proc = _run_cli("verify", "--report", str(tampered))
    assert proc.returncode == 1


def test_verify_report_missing_file():
    proc = _run_cli("verify", "--report", "output/runs/no-such-run/report.json")
    assert proc.returncode == 2


def test_verify_suite_and_report_mutually_exclusive(healthy_run):
    proc = _run_cli(
        "verify",
        "--suite",
        "s0",
        "--report",
        str(healthy_run["out_dir"] / "report.json"),
    )
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# report preview / export
# ---------------------------------------------------------------------------


def test_report_preview_writes_nothing(healthy_run):
    out_dir = healthy_run["out_dir"]
    before = {
        p.name: (p.stat().st_mtime_ns, p.stat().st_size)
        for p in out_dir.iterdir()
    }
    time.sleep(0.01)
    proc = _run_cli("report", "preview", str(out_dir / "report.json"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PRIVACY PREVIEW" in proc.stdout
    assert "verdict:       PASS_OBSERVED" in proc.stdout
    assert "001 ORIGIN_HTML" in proc.stdout
    after = {
        p.name: (p.stat().st_mtime_ns, p.stat().st_size)
        for p in out_dir.iterdir()
    }
    assert before == after


def test_report_export_writes_clean_html(healthy_run):
    out_dir = healthy_run["out_dir"]
    html_path = out_dir / "preview-export.html"
    if html_path.exists():
        html_path.unlink()
    proc = _run_cli(
        "report", "export", str(out_dir / "report.json"), "--out", str(html_path)
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PRIVACY PREVIEW" in proc.stdout
    assert html_path.is_file()
    text = html_path.read_text(encoding="utf-8")
    assert healthy_run["report"]["report_hash"] in text
    assert '"verdict": "PASS_OBSERVED"' in text
    from accepttwin.privacy import scan_html_for_remote_resources

    assert scan_html_for_remote_resources(text) == []
    assert "AT_HTML_SENTINEL_001" not in text
    assert "AT_MARKDOWN_SENTINEL_001" not in text


def test_report_export_default_out_next_to_report(healthy_run):
    out_dir = healthy_run["out_dir"]
    html_path = out_dir / "report.html"
    if html_path.exists():
        html_path.unlink()
    proc = _run_cli("report", "export", str(out_dir / "report.json"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert html_path.is_file()


def test_report_export_check_only_writes_nothing(healthy_run):
    out_dir = healthy_run["out_dir"]
    before = sorted(p.name for p in out_dir.iterdir())
    proc = _run_cli(
        "report", "export", str(out_dir / "report.json"), "--check-only"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHECK ONLY" in proc.stdout
    assert sorted(p.name for p in out_dir.iterdir()) == before


def test_report_preview_missing_file():
    proc = _run_cli("report", "preview", "output/runs/no-such-run/report.json")
    assert proc.returncode == 2


def test_report_export_invalid_report(healthy_run, tmp_path):
    report = dict(healthy_run["report"])
    report["verdict"] = "CONTRACT_MISMATCH"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(report), encoding="utf-8")
    proc = _run_cli("report", "export", str(tampered))
    assert proc.returncode == 1


# ---------------------------------------------------------------------------
# report delete / contract delete (safety boundaries)
# ---------------------------------------------------------------------------


def _copy_report_to_run_dir(run_id: str) -> Path:
    out_dir = _tracked_run_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "report.json"
    target.write_text(
        (RUNS_DIR / "cli-test-healthy" / "report.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return target


def test_report_delete_removes_report(healthy_run):
    target = _copy_report_to_run_dir("cli-test-del-report")
    proc = _run_cli("report", "delete", str(target))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "deleted:" in proc.stdout
    assert not target.exists()


def test_report_delete_refuses_non_report():
    out_dir = _tracked_run_dir("cli-test-del-nonreport")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "contract.json"
    target.write_text(
        HEALTHY_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    proc = _run_cli("report", "delete", str(target))
    assert proc.returncode == 2
    assert target.exists(), "refused delete must not delete the file"


def test_report_delete_refuses_outside_workspace(healthy_run, tmp_path):
    victim = tmp_path / "victim-report.json"
    victim.write_text(
        (healthy_run["out_dir"] / "report.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    proc = _run_cli("report", "delete", str(victim))
    assert proc.returncode == 2
    assert victim.exists()


def test_report_delete_refuses_symlink(healthy_run):
    out_dir = _tracked_run_dir("cli-test-del-symlink")
    out_dir.mkdir(parents=True, exist_ok=True)
    real = healthy_run["out_dir"] / "report.json"
    link = out_dir / "report.json"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(real)
    proc = _run_cli("report", "delete", str(link))
    assert proc.returncode == 2
    assert real.exists()
    assert link.is_symlink()
    link.unlink()


def test_report_delete_refuses_directory(healthy_run):
    proc = _run_cli("report", "delete", str(healthy_run["out_dir"]))
    assert proc.returncode == 2


def test_report_delete_missing_file():
    proc = _run_cli("report", "delete", "output/runs/no-such-run/report.json")
    assert proc.returncode == 2


def test_contract_delete_removes_contract():
    out_dir = _tracked_run_dir("cli-test-del-contract")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "contract.json"
    target.write_text(HEALTHY_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    proc = _run_cli("contract", "delete", str(target))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not target.exists()


def test_contract_delete_refuses_non_contract(healthy_run):
    target = _copy_report_to_run_dir("cli-test-del-noncontract")
    proc = _run_cli("contract", "delete", str(target))
    assert proc.returncode == 2
    assert target.exists()


def test_contract_delete_refuses_outside_workspace(tmp_path):
    victim = tmp_path / "victim-contract.json"
    victim.write_text(HEALTHY_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    proc = _run_cli("contract", "delete", str(victim))
    assert proc.returncode == 2
    assert victim.exists()


def test_contract_delete_refuses_symlink():
    out_dir = _tracked_run_dir("cli-test-del-contract-symlink")
    out_dir.mkdir(parents=True, exist_ok=True)
    link = out_dir / "contract.json"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(HEALTHY_CONTRACT)
    proc = _run_cli("contract", "delete", str(link))
    assert proc.returncode == 2
    assert HEALTHY_CONTRACT.exists()
    assert link.is_symlink()
    link.unlink()


# ---------------------------------------------------------------------------
# clean --run-id
# ---------------------------------------------------------------------------


def test_clean_deletes_run_dir():
    run_id = "cli-test-clean"
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--run-id", run_id
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _tracked_run_dir(run_id).is_dir()
    proc = _run_cli("clean", "--run-id", run_id)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CLEAN_STATUS: OK" in proc.stdout
    assert not _tracked_run_dir(run_id).exists()


def test_clean_dry_run_deletes_nothing():
    run_id = "cli-test-clean-dry"
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--run-id", run_id
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    before = sorted(p.name for p in _tracked_run_dir(run_id).iterdir())
    proc = _run_cli("clean", "--run-id", run_id, "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DRY-RUN" in proc.stdout
    assert sorted(p.name for p in _tracked_run_dir(run_id).iterdir()) == before
    proc = _run_cli("clean", "--run-id", run_id)
    assert proc.returncode == 0


def test_clean_missing_run():
    proc = _run_cli("clean", "--run-id", "no-such-run")
    assert proc.returncode == 2


def test_clean_traversal_run_id():
    # "../custom-healthy-001" would escape output/runs/ if resolved;
    # the run-id validator must refuse it before anything is touched.
    assert not (ROOT / "output" / "custom-healthy-001").exists()
    proc = _run_cli("clean", "--run-id", "../custom-healthy-001")
    assert proc.returncode == 2
    assert not (ROOT / "output" / "custom-healthy-001").exists()


def test_clean_refuses_symlink_inside():
    run_id = "cli-test-clean-symlink"
    out_dir = _tracked_run_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    victim = out_dir / "keep.txt"
    victim.write_text("keep", encoding="utf-8")
    link = out_dir / "link.json"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(victim)
    proc = _run_cli("clean", "--run-id", run_id)
    assert proc.returncode == 2
    assert victim.exists()
    assert out_dir.is_dir()
    link.unlink()
    victim.unlink()
    out_dir.rmdir()


def test_clean_refuses_symlink_run_dir(tmp_path):
    real = tmp_path / "real-run"
    real.mkdir()
    (real / "report.json").write_text("{}", encoding="utf-8")
    link = RUNS_DIR / "cli-test-clean-linkdir"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(real)
    proc = _run_cli("clean", "--run-id", "cli-test-clean-linkdir")
    assert proc.returncode == 2
    assert (real / "report.json").exists()
    link.unlink()


# ---------------------------------------------------------------------------
# help / docs surface
# ---------------------------------------------------------------------------


def test_help_lists_all_commands():
    proc = _run_cli("--help")
    assert proc.returncode == 0, proc.stderr
    for name in ("run", "demo", "verify", "report", "clean", "contract", "benchmark"):
        assert name in proc.stdout


def test_report_subcommand_help_lists_preview_export_delete():
    proc = _run_cli("report", "--help")
    assert proc.returncode == 0, proc.stderr
    for name in ("preview", "export", "delete"):
        assert name in proc.stdout


def test_docs_name_the_new_commands():
    for doc in (ROOT / "README.md", ROOT / "docs" / "USAGE.md"):
        text = doc.read_text(encoding="utf-8")
        assert "accepttwin run --contract" in text
        assert "accepttwin demo" in text
        assert "accepttwin verify --report" in text
        assert "accepttwin report preview" in text
        assert "accepttwin report export" in text
        assert "accepttwin clean --run-id" in text
```

## tests/integration/test_experiment_runner.py

- SHA-256：`d1c96bc8a96fd7199570327dd71dd35ee2ac3420e33cc3129d7436fd660a7584`
- 字节数：20527

```
"""Integration tests for the four-experiment runner (P032 T005).

Acceptance criteria (IMPLEMENTATION_PLAN T005 / PROJECT_BOOK §6,
§10.2):

1. Every scenario has O-H, O-M, H-COLD, M-COLD, H->M, M->H.
2. Each warm-cache order contains two real requests.
3. A reset record exists between the four experiments.
4. No reset happens between the two requests of a warm experiment.
5. At least one healthy and one bleed scenario really complete all
   four experiments.
6. (Hard requirement, T002 review P2-03) The HTTP client never reads
   proxy environment variables: with HTTP_PROXY/HTTPS_PROXY pointing
   at a dead proxy, the run still succeeds.

Every test makes real HTTP requests over localhost (``http.client``
inside the runner, never a preset report). The origin and the proxy
bind OS-assigned loopback ports (``port=0``) except for the one test
that exercises runner-owned services on explicitly allocated ports.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import socket
from pathlib import Path

import pytest

from accepttwin.cache_evidence import CACHE_STATE_UNKNOWN
from accepttwin.contract import parse_contract
from accepttwin.evidence import (
    RAW_OBSERVATIONS_FORMAT,
    read_evidence_file,
)
from accepttwin.experiment_runner import (
    STEP_NAMES,
    ExperimentError,
    ExperimentRun,
    run_experiments,
)
from accepttwin.cache_proxy import ControlledCacheProxy
from accepttwin.origin_server import (
    HTML_SENTINEL,
    MARKDOWN_SENTINEL,
    SyntheticOrigin,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

HTML_ACCEPT = "text/html"
MARKDOWN_ACCEPT = "text/markdown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_contract(proxy_url: str, origin_url: str, *, mode="variant_by_accept"):
    """A valid contract pointing at the given live service URLs."""
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = proxy_url
    data["origin_url"] = origin_url
    if mode == "no_store":
        data["cache_behavior"] = {
            "mode": "no_store",
            "vary_accept": "not_required",
            "max_age_seconds": None,
        }
    else:
        data["cache_behavior"] = {
            "mode": "variant_by_accept",
            "vary_accept": "advisory",
            "max_age_seconds": 60,
        }
    return parse_contract(data)


class Pair:
    """A running (origin, proxy, contract) triple; use as a context manager."""

    def __init__(self, mode, scenario="healthy", *, no_store=False):
        self.origin = SyntheticOrigin(port=0, scenario=scenario)
        self.origin.start()
        kwargs: dict = {"port": 0, "mode": mode, "origin_url": self.origin.url}
        self.proxy = ControlledCacheProxy(**kwargs)
        self.proxy.start()
        if no_store:
            contract = build_contract(self.proxy.url, self.origin.url, mode="no_store")
            self.proxy.stop()
            self.proxy = ControlledCacheProxy(
                port=0, mode=mode, contract=contract
            )
            self.proxy.start()
            # The rebuilt proxy binds a new port: rebuild the contract.
            contract = build_contract(self.proxy.url, self.origin.url, mode="no_store")
        else:
            contract = build_contract(self.proxy.url, self.origin.url)
        self.contract = contract

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.proxy.stop()
        self.origin.stop()
        return False


def run_pair(pair: Pair, **kwargs) -> ExperimentRun:
    return run_experiments(
        pair.contract, origin=pair.origin, proxy=pair.proxy, **kwargs
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Frozen order, request numbers, one URL per leg
# ---------------------------------------------------------------------------


def test_frozen_step_order_and_request_numbers():
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    assert [rec.name for rec in run.step_log] == list(STEP_NAMES)
    assert [rec.step for rec in run.step_log] == list(range(1, 26))
    assert len(run.observations) == 8
    assert [obs.request_index for obs in run.observations] == list(range(1, 9))
    assert [obs.experiment_id for obs in run.observations] == [
        "ORIGIN_HTML",
        "ORIGIN_MARKDOWN",
        "HTML_COLD",
        "MARKDOWN_COLD",
        "HTML_TO_MARKDOWN",
        "HTML_TO_MARKDOWN",
        "MARKDOWN_TO_HTML",
        "MARKDOWN_TO_HTML",
    ]
    assert [obs.requested_representation for obs in run.observations] == [
        "html", "markdown", "html", "markdown",
        "html", "markdown", "markdown", "html",
    ]
    # One URL string per leg: direct requests use origin_url, proxied
    # requests all use the same contract url (§6.2).
    assert [raw.url for raw in run.raw_observations[:2]] == [
        pair.contract.origin_url,
        pair.contract.origin_url,
    ]
    assert {raw.url for raw in run.raw_observations[2:]} == {
        pair.contract.url,
    }
    assert [raw.method for raw in run.raw_observations] == ["GET"] * 8
    assert [raw.accept for raw in run.raw_observations] == [
        HTML_ACCEPT, MARKDOWN_ACCEPT, HTML_ACCEPT, MARKDOWN_ACCEPT,
        HTML_ACCEPT, MARKDOWN_ACCEPT, MARKDOWN_ACCEPT, HTML_ACCEPT,
    ]


def test_request_observation_matches_spec_5_5_fields():
    from accepttwin.evidence import RequestObservation

    names = {f.name for f in dataclasses.fields(RequestObservation)}
    assert names == {
        "request_index",
        "experiment_id",
        "requested_representation",
        "response_status",
        "response_content_type",
        "body_sha256",
        "sentinel_match",
        "cache_status",
        "cache_key_sha256",
        "cache_entry_id",
        "origin_counter_before",
        "origin_counter_after",
        "origin_counter_delta",
    }


# ---------------------------------------------------------------------------
# Healthy scenario: all four experiments complete
# ---------------------------------------------------------------------------


def test_healthy_scenario_completes_four_experiments():
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    assert all(obs.response_status == 200 for obs in run.observations)
    assert all(obs.sentinel_match for obs in run.observations)
    assert all(raw.transport_error is None for raw in run.raw_observations)
    # Direct baselines carry no cache state; every proxied request is
    # a verified MISS in a healthy respect_vary setup.
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "MISS", "MISS", "MISS",
    ]
    # Every request reached the origin exactly once (8 requests, 8
    # origin events, counter delta 8).
    assert run.origin_counter_final - run.origin_counter_baseline == 8
    assert [obs.origin_counter_delta for obs in run.observations] == [1] * 8
    assert len(run.origin_events) == 8
    assert run.verification_failures == ()
    assert len(run.step_log) == 25
    assert all(rec.ok for rec in run.step_log)


def test_resets_between_experiments_and_empty_before_each_cold():
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    # Exactly four resets, at the frozen steps 09/13/17/22 only.
    assert len(run.reset_evidence) == 4
    assert all(ev.success and ev.entries_after == 0 for ev in run.reset_evidence)
    assert [rec.step for rec in run.step_log if rec.name == "ResetCache"] == [
        9, 13, 17, 22,
    ]
    assert [ev.namespace for ev in run.reset_evidence] == [
        "t005-html-cold",
        "t005-markdown-cold",
        "t005-html-to-markdown",
        "t005-markdown-to-html",
    ]
    # Each cold / warm-first request starts from an empty cache.
    assert run.raw_observations[2].cache_entry_count_before == 0  # 003 H-COLD
    assert run.raw_observations[3].cache_entry_count_before == 0  # 004 M-COLD
    assert run.raw_observations[4].cache_entry_count_before == 0  # 005 HM-1
    assert run.raw_observations[6].cache_entry_count_before == 0  # 007 MH-1


def test_warm_experiments_have_two_real_requests_no_reset_between():
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    # Steps 19-20 and 24-25 are consecutive request steps with no
    # ResetCache step between them (§6.2 / §10.2).
    names = [rec.name for rec in run.step_log]
    assert names[18:20] == ["HTMLWarmFirst", "MarkdownWarmSecond"]
    assert names[23:25] == ["MarkdownWarmFirst", "HTMLWarmSecond"]
    for number in (5, 6, 7, 8):
        raw = run.raw_observations[number - 1]
        assert raw.transport_error is None
        assert raw.response_status == 200
        assert raw.origin_event_present is True
    # The two requests of each warm experiment are distinct origin
    # events, in order (H then M; M then H).
    accepts = [ev.accept for ev in run.origin_events]
    assert accepts == [
        HTML_ACCEPT, MARKDOWN_ACCEPT, HTML_ACCEPT, MARKDOWN_ACCEPT,
        HTML_ACCEPT, MARKDOWN_ACCEPT, MARKDOWN_ACCEPT, HTML_ACCEPT,
    ]


# ---------------------------------------------------------------------------
# Bleed scenario: all four experiments complete, bleed visible
# ---------------------------------------------------------------------------


def test_bleed_scenario_completes_four_experiments():
    with Pair("force_uri_only") as pair:
        run = run_pair(pair, proxy_mode="force_uri_only")
    assert len(run.observations) == 8
    assert all(raw.transport_error is None for raw in run.raw_observations)
    # Cold requests are MISS; each warm second request HITs the first
    # representation's entry (verified dual evidence, §5.3 B).
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "HIT", "MISS", "HIT",
    ]
    # HM-2 asked for Markdown but got the HTML body; MH-2 the reverse.
    assert run.observations[5].sentinel_match is False  # 006 HM-2
    assert run.observations[7].sentinel_match is False  # 008 MH-2
    assert run.observations[5].body_sha256 == run.observations[4].body_sha256
    assert run.observations[7].body_sha256 == run.observations[6].body_sha256
    # HITs did not reach the origin: 6 origin requests, not 8.
    assert run.origin_counter_final - run.origin_counter_baseline == 6
    assert [obs.origin_counter_delta for obs in run.observations] == [
        1, 1, 1, 1, 1, 0, 1, 0,
    ]
    assert run.verification_failures == ()


def test_respect_vary_without_vary_bleeds_both_orders():
    # §11.2 C13/C14: no Vary + respect_vary keys on the URI only.
    with Pair("respect_vary", scenario="no_vary") as pair:
        run = run_pair(pair)
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "HIT", "MISS", "HIT",
    ]
    assert run.observations[5].sentinel_match is False
    assert run.observations[7].sentinel_match is False


def test_manual_accept_key_healthy_without_vary():
    # §11.2 C03/C04: missing Vary alone is not a fault.
    with Pair("manual_accept_key", scenario="no_vary") as pair:
        run = run_pair(pair, proxy_mode="manual_accept_key")
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "MISS", "MISS", "MISS",
    ]
    assert all(obs.sentinel_match for obs in run.observations)
    assert run.verification_failures == ()


# ---------------------------------------------------------------------------
# no-store / opaque / origin-fault scenarios still run all four experiments
# ---------------------------------------------------------------------------


def test_no_store_bypass_scenario():
    with Pair("disabled", no_store=True) as pair:
        run = run_pair(pair, proxy_mode="disabled")
    assert len(run.observations) == 8
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "BYPASS", "BYPASS", "BYPASS", "BYPASS", "BYPASS", "BYPASS",
    ]
    assert all(obs.sentinel_match for obs in run.observations)
    assert all(
        raw.cache_entry_count_after == 0 for raw in run.raw_observations[2:]
    )
    assert run.verification_failures == ()


def test_origin_fault_still_completes_all_experiments():
    # §11.2 C07: the HTML baseline is a 404, but the run must still
    # collect the remaining requests so the first error stays locatable.
    with Pair("respect_vary", scenario="html_404") as pair:
        run = run_pair(pair)
    assert len(run.observations) == 8
    assert run.observations[0].response_status == 404  # 001 O-H
    assert run.observations[1].response_status == 200  # 002 O-M
    assert all(raw.transport_error is None for raw in run.raw_observations)
    assert len(run.origin_events) == 8


def test_opaque_unknown_evidence_does_not_abort_run():
    # §11.2 C20: header evidence is hidden, so cache states are
    # UNKNOWN — but all eight requests still run and are recorded.
    with Pair("opaque") as pair:
        run = run_pair(pair, proxy_mode="opaque")
    assert len(run.observations) == 8
    assert [obs.cache_status for obs in run.observations[2:]] == [
        CACHE_STATE_UNKNOWN
    ] * 6
    assert run.verification_failures, "VerifyMissOrBypass must fail, not abort"
    assert len(run.step_log) == 25


# ---------------------------------------------------------------------------
# Hard requirement: proxy environment variables are never used (P2-03)
# ---------------------------------------------------------------------------


def test_proxy_environment_variables_ignored(monkeypatch):
    # Point every proxy variable at a dead proxy. If the client honoured
    # any of them, every request would fail; http.client never reads them.
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:1"
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    assert len(run.observations) == 8
    assert all(obs.response_status == 200 for obs in run.observations)
    assert all(raw.transport_error is None for raw in run.raw_observations)
    assert run.verification_failures == ()


def test_proxy_environment_variables_ignored_in_bleed_run(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "example.invalid")
    with Pair("force_uri_only") as pair:
        run = run_pair(pair, proxy_mode="force_uri_only")
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "HIT", "MISS", "HIT",
    ]


# ---------------------------------------------------------------------------
# Evidence file (T006 / T007 input): round-trip, no body text
# ---------------------------------------------------------------------------


def test_evidence_file_roundtrip_and_no_body_text(tmp_path):
    with Pair("force_uri_only") as pair:
        out = tmp_path / "raw-observations.json"
        run = run_pair(pair, output_path=out, proxy_mode="force_uri_only")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # No response body text may enter the evidence file (§7.12 I-12):
    # neither the HTML body nor the Markdown body, nor either Sentinel
    # string (only its SHA-256 is recorded).
    assert "<!DOCTYPE html>" not in text
    assert "# AcceptTwin synthetic document" not in text
    assert HTML_SENTINEL not in text
    assert MARKDOWN_SENTINEL not in text
    assert "body_text" not in text
    assert "response_body" not in text
    data = read_evidence_file(out)
    assert data["format"] == RAW_OBSERVATIONS_FORMAT
    assert data["contract_id"] == pair.contract.contract_id
    assert len(data["observations"]) == 8
    assert len(data["steps"]) == 25
    assert [s["name"] for s in data["steps"]] == list(STEP_NAMES)
    assert len(data["resets"]) == 4
    assert len(data["origin_events"]) == 6  # bleed run: 2 HITs, no origin hit
    assert data["origin_counter_baseline"] == 0
    assert data["origin_counter_final"] == 6
    # The §5.5 projection is recoverable from each raw observation.
    for raw in data["observations"]:
        assert hashlib.sha256(b"").hexdigest() != raw["body_sha256"]
        assert len(raw["body_sha256"]) == 64
        assert len(raw["sentinel_sha256"]) == 64
        assert raw["cache_status_header"] in (
            None, "MISS", "HIT", "BYPASS",
        )
    # The run object and the file agree.
    assert run.as_dict() == data


def test_evidence_file_rejects_wrong_format(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "other/v1"}), encoding="utf-8")
    with pytest.raises(ValueError, match="format"):
        read_evidence_file(bad)


# ---------------------------------------------------------------------------
# Runner-owned services and contract validation
# ---------------------------------------------------------------------------


def test_runner_creates_and_stops_own_services():
    origin_port = free_port()
    proxy_port = free_port()
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = f"http://127.0.0.1:{proxy_port}/doc"
    data["origin_url"] = f"http://127.0.0.1:{origin_port}/doc"
    contract = parse_contract(data)
    run = run_experiments(contract, scenario="healthy", proxy_mode="respect_vary")
    assert len(run.observations) == 8
    assert all(obs.response_status == 200 for obs in run.observations)
    assert run.verification_failures == ()
    # Services the runner created are stopped again afterwards.
    assert not port_open(origin_port)
    assert not port_open(proxy_port)


def test_non_loopback_contract_rejected():
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = "http://93.184.216.34/doc"
    data["origin_url"] = "http://93.184.216.34:18766/doc"
    with pytest.raises((ExperimentError, ValueError)):
        run_experiments(data)


def test_supplied_origin_disagreeing_with_contract_rejected():
    with Pair("respect_vary") as pair:
        other_origin = SyntheticOrigin(port=0, scenario="healthy")
        other_origin.start()
        try:
            with pytest.raises(ExperimentError, match="disagrees"):
                run_experiments(
                    pair.contract, origin=other_origin, proxy=pair.proxy
                )
        finally:
            other_origin.stop()


def test_supplied_proxy_with_mismatched_mode_rejected():
    # Step 04 fail-closed (T005 review P2-4): a supplied proxy whose
    # mode disagrees with the mode the run was asked to use is
    # rejected before any request is sent. Here a "force_uri_only"
    # proxy is supplied against a "variant_by_accept" contract with
    # the default proxy_mode ("respect_vary"): the modes disagree,
    # so the run raises instead of silently proceeding under the
    # wrong proxy mode. A deliberate bleed run must declare its mode
    # explicitly via proxy_mode="force_uri_only".
    with Pair("force_uri_only") as pair:
        with pytest.raises(ExperimentError, match="disagrees"):
            run_pair(pair)


def test_ports_not_listening_rejected(monkeypatch):
    # Step 05 fail-closed: if the port check reports a service down,
    # the run raises before any request is sent (simulated here by
    # stubbing the check — a runner-created service always listens,
    # so the live path cannot produce this state on its own).
    monkeypatch.setattr(
        "accepttwin.experiment_runner._check_port_listening",
        lambda *args, **kwargs: False,
    )
    with Pair("respect_vary") as pair:
        with pytest.raises(ExperimentError, match="not listening"):
            run_pair(pair)
```

## tests/integration/test_origin_server.py

- SHA-256：`20bae5f1516c072451991fb2db9f6686f27447ae91576ed5e759d0f601bcc565`
- 字节数：21107

```
"""Integration tests for the synthetic origin server (P032 T003).

Acceptance criteria (IMPLEMENTATION_PLAN T003):

1. HTML Accept returns HTML.
2. Markdown Accept returns Markdown.
3. The two Sentinels are different.
4. Origin status is controllable (fault fixtures).
5. Origin Content-Type is controllable (fault fixtures).
6. Request counting is accurate.
7. Event order is accurate.
8. Response bodies are not written to ordinary logs.
9. The port is released after the server stops.

Every test makes real HTTP requests over localhost (``http.client``,
no proxy — the origin never consults proxy environment variables).
Servers bind an OS-assigned loopback port (``port=0``) except for the
one test that pins the frozen default port 18766 from
``contracts/site.json``.
"""

from __future__ import annotations

import http.client
import json
import logging
import socket
from pathlib import Path

import pytest

from accepttwin.contract import load_contract
from accepttwin.origin_server import (
    DEFAULT_PORT,
    HTML_SENTINEL,
    MARKDOWN_SENTINEL,
    OriginServerError,
    ScenarioError,
    SyntheticOrigin,
    default_fixture_dir,
    load_scenario,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

HTML_ACCEPT = "text/html"
MARKDOWN_ACCEPT = "text/markdown"


def get(port: int, path: str = "/doc", accept: str = HTML_ACCEPT):
    """One real GET over loopback; returns (status, headers dict, body)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers={"Accept": accept})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        conn.close()


@pytest.fixture()
def origin():
    """A healthy origin on an OS-assigned loopback port."""
    server = SyntheticOrigin(port=0, scenario="healthy")
    server.start()
    yield server
    server.stop()


@pytest.fixture()
def contract():
    return load_contract(CONTRACT_PATH)


# ---------------------------------------------------------------------------
# AC1: HTML Accept returns HTML
# ---------------------------------------------------------------------------


def test_html_accept_returns_html(origin):
    status, headers, body = get(origin.port, accept=HTML_ACCEPT)
    assert status == 200
    assert headers["content-type"] == "text/html; charset=utf-8"
    text = body.decode("utf-8")
    assert HTML_SENTINEL in text
    assert MARKDOWN_SENTINEL not in text
    assert text.lstrip().lower().startswith("<!doctype html>")
    assert headers.get("vary") == "Accept"


# ---------------------------------------------------------------------------
# AC2: Markdown Accept returns Markdown
# ---------------------------------------------------------------------------


def test_markdown_accept_returns_markdown(origin):
    status, headers, body = get(origin.port, accept=MARKDOWN_ACCEPT)
    assert status == 200
    assert headers["content-type"] == "text/markdown; charset=utf-8"
    text = body.decode("utf-8")
    assert MARKDOWN_SENTINEL in text
    assert HTML_SENTINEL not in text
    assert text.startswith("# AcceptTwin synthetic document")


# ---------------------------------------------------------------------------
# AC3: the two Sentinels are different
# ---------------------------------------------------------------------------


def test_sentinels_are_different(contract):
    html_sentinel = contract.representations["html"].sentinel
    markdown_sentinel = contract.representations["markdown"].sentinel
    assert html_sentinel != markdown_sentinel
    assert html_sentinel == HTML_SENTINEL
    assert markdown_sentinel == MARKDOWN_SENTINEL
    # Each body carries exactly one Sentinel occurrence, and only its own.
    origin = SyntheticOrigin(port=0, scenario="healthy")
    origin.start()
    try:
        _, _, html_body = get(origin.port, accept=HTML_ACCEPT)
        _, _, md_body = get(origin.port, accept=MARKDOWN_ACCEPT)
    finally:
        origin.stop()
    assert html_body.decode("utf-8").count(HTML_SENTINEL) == 1
    assert md_body.decode("utf-8").count(MARKDOWN_SENTINEL) == 1


# ---------------------------------------------------------------------------
# AC4: origin status is controllable (fault fixtures)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario, html_status, md_status",
    [
        ("markdown_404", 200, 404),
        ("html_404", 404, 200),
    ],
)
def test_status_fault_fixture(scenario, html_status, md_status):
    server = SyntheticOrigin(port=0, scenario=scenario)
    server.start()
    try:
        h_status, _, _ = get(server.port, accept=HTML_ACCEPT)
        m_status, _, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_status == html_status
    assert m_status == md_status


def test_healthy_fixture_is_200_for_both():
    server = SyntheticOrigin(port=0, scenario="healthy")
    server.start()
    try:
        assert get(server.port, accept=HTML_ACCEPT)[0] == 200
        assert get(server.port, accept=MARKDOWN_ACCEPT)[0] == 200
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# AC5: origin Content-Type is controllable (fault fixtures)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario, html_ct, md_ct",
    [
        (
            "html_wrong_content_type",
            "text/plain; charset=utf-8",
            "text/markdown; charset=utf-8",
        ),
        (
            "markdown_wrong_content_type",
            "text/html; charset=utf-8",
            "text/html; charset=utf-8",
        ),
    ],
)
def test_content_type_fault_fixture(scenario, html_ct, md_ct):
    server = SyntheticOrigin(port=0, scenario=scenario)
    server.start()
    try:
        _, h_headers, _ = get(server.port, accept=HTML_ACCEPT)
        _, m_headers, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_headers["content-type"] == html_ct
    assert m_headers["content-type"] == md_ct


# ---------------------------------------------------------------------------
# AC5b/AC4b: Sentinel is controllable (fault fixtures)
# ---------------------------------------------------------------------------


def test_sentinel_fault_fixtures():
    server = SyntheticOrigin(port=0, scenario="markdown_sentinel_missing")
    server.start()
    try:
        _, _, md_body = get(server.port, accept=MARKDOWN_ACCEPT)
        _, _, html_body = get(server.port, accept=HTML_ACCEPT)
    finally:
        server.stop()
    assert MARKDOWN_SENTINEL not in md_body.decode("utf-8")
    assert HTML_SENTINEL in html_body.decode("utf-8")

    server = SyntheticOrigin(port=0, scenario="html_sentinel_wrong")
    server.start()
    try:
        _, _, html_body = get(server.port, accept=HTML_ACCEPT)
    finally:
        server.stop()
    text = html_body.decode("utf-8")
    assert HTML_SENTINEL not in text
    assert "AT_HTML_SENTINEL_999" in text


# ---------------------------------------------------------------------------
# AC6: request counting is accurate
# ---------------------------------------------------------------------------


def test_request_count_is_accurate(origin):
    before = origin.counter_snapshot()
    assert before.total_requests == 0
    get(origin.port, accept=HTML_ACCEPT)
    get(origin.port, accept=HTML_ACCEPT)
    get(origin.port, accept=MARKDOWN_ACCEPT)
    get(origin.port, accept="application/json")  # 406, still a request
    get(origin.port, path="/other", accept=HTML_ACCEPT)  # 404, still a request
    after = origin.counter_snapshot()
    assert after.total_requests == before.total_requests + 5
    assert after.html_requests == 3  # 2 x /doc HTML + 1 x /other HTML
    assert after.markdown_requests == 1
    assert after.other_requests == 1  # the application/json request


def test_counter_delta_matches_requests_across_scenarios():
    server = SyntheticOrigin(port=0, scenario="markdown_404")
    server.start()
    try:
        before = server.counter_snapshot()
        get(server.port, accept=MARKDOWN_ACCEPT)  # 404 still counts
        get(server.port, accept=MARKDOWN_ACCEPT)
        after = server.counter_snapshot()
    finally:
        server.stop()
    assert after.total_requests - before.total_requests == 2
    assert after.markdown_requests - before.markdown_requests == 2


# ---------------------------------------------------------------------------
# AC7: event order is accurate
# ---------------------------------------------------------------------------


def test_event_log_order_is_accurate(origin):
    plan = [
        ("GET", "/doc", HTML_ACCEPT, 200),
        ("GET", "/doc", MARKDOWN_ACCEPT, 200),
        ("GET", "/doc", HTML_ACCEPT, 200),
        ("GET", "/other", HTML_ACCEPT, 404),
        ("GET", "/doc", "application/json", 406),
    ]
    for _, path, accept, _ in plan:
        get(origin.port, path=path, accept=accept)
    events = origin.event_log()
    assert len(events) == len(plan)
    for i, (event, (method, path, accept, status)) in enumerate(zip(events, plan), start=1):
        assert event.index == i
        assert event.method == method
        assert event.path == path
        assert event.accept == accept
        assert event.status == status
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps), "event timestamps must be monotonic"
    assert all(t2 >= t1 for t1, t2 in zip(timestamps, timestamps[1:]))
    # The log is a snapshot copy: mutating it must not corrupt the origin.
    events.clear()
    assert len(origin.event_log()) == len(plan)


# ---------------------------------------------------------------------------
# AC8: response bodies are not written to ordinary logs
# ---------------------------------------------------------------------------


def test_body_not_written_to_ordinary_logs(origin, caplog):
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = CaptureHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    old_level = root.level
    root.setLevel(logging.DEBUG)
    logging.getLogger("accepttwin").setLevel(logging.DEBUG)
    try:
        with caplog.at_level(logging.DEBUG):
            get(origin.port, accept=HTML_ACCEPT)
            get(origin.port, accept=MARKDOWN_ACCEPT)
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    forbidden = [
        HTML_SENTINEL,
        MARKDOWN_SENTINEL,
        "AcceptTwin synthetic document",
        "Synthetic Markdown representation",
    ]
    for record in records:
        message = record.getMessage()
        for fragment in forbidden:
            assert fragment not in message, f"log record leaks body text: {message!r}"
    for fragment in forbidden:
        assert fragment not in caplog.text


# ---------------------------------------------------------------------------
# AC9: the port is released after the server stops
# ---------------------------------------------------------------------------


def test_port_released_after_stop():
    server = SyntheticOrigin(port=0, scenario="healthy")
    server.start()
    port = server.port
    assert get(port, accept=HTML_ACCEPT)[0] == 200
    server.stop()
    assert not server.is_running
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
    # The same port can be bound again immediately.
    again = SyntheticOrigin(port=port, scenario="healthy")
    again.start()
    try:
        assert get(port, accept=MARKDOWN_ACCEPT)[0] == 200
    finally:
        again.stop()


def test_stop_is_idempotent():
    server = SyntheticOrigin(port=0, scenario="healthy")
    server.start()
    server.stop()
    server.stop()  # must not raise


# ---------------------------------------------------------------------------
# Contract / default-port wiring (§5.1.1)
# ---------------------------------------------------------------------------


def test_default_port_matches_contract_origin_url(contract):
    assert contract.origin_url == f"http://127.0.0.1:{DEFAULT_PORT}/doc"
    assert DEFAULT_PORT == 18766
    server = SyntheticOrigin(contract=contract)
    assert server.port == 18766
    assert server.url == contract.origin_url
    server.start()
    try:
        assert get(18766, accept=HTML_ACCEPT)[0] == 200
    finally:
        server.stop()


def test_explicit_values_disagreeing_with_contract_are_rejected(contract):
    with pytest.raises(OriginServerError):
        SyntheticOrigin(contract=contract, port=19999)
    with pytest.raises(OriginServerError):
        SyntheticOrigin(contract=contract, path="/other")


def test_double_start_is_rejected(origin):
    with pytest.raises(OriginServerError):
        origin.start()


def test_non_loopback_host_is_rejected():
    with pytest.raises(OriginServerError):
        SyntheticOrigin(host="8.8.8.8", port=0)


# ---------------------------------------------------------------------------
# Scenario loading (fail-closed)
# ---------------------------------------------------------------------------


def test_all_fixture_files_load_and_validate():
    names = sorted(p.stem for p in default_fixture_dir().glob("*.json"))
    assert names == [
        "cache_max_age_0",
        "cache_no_cache",
        "healthy",
        "html_404",
        "html_markdown_content_type",
        "html_sentinel_wrong",
        "html_wrong_content_type",
        "markdown_404",
        "markdown_406",
        "markdown_sentinel_missing",
        "markdown_wrong_content_type",
        "no_vary",
        "vary_lowercase",
        "vary_multi",
        "vary_star",
    ]
    for name in names:
        scenario = load_scenario(name)
        assert scenario["scenario_id"] == name
        assert set(scenario["representations"]) == {"html", "markdown"}


def test_unknown_scenario_is_rejected():
    with pytest.raises(ScenarioError):
        load_scenario("does_not_exist")


def test_scenario_with_unknown_field_is_rejected(tmp_path):
    bad = {
        "scenario_id": "bad",
        "representations": {
            "html": {"status": 200, "surprise": True},
            "markdown": {"status": 200},
        },
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario(path)


def test_no_vary_fixture_serves_bodies_without_vary():
    server = SyntheticOrigin(port=0, scenario="no_vary")
    server.start()
    try:
        _, h_headers, h_body = get(server.port, accept=HTML_ACCEPT)
        _, m_headers, m_body = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert "vary" not in h_headers
    assert "vary" not in m_headers
    assert HTML_SENTINEL in h_body.decode("utf-8")
    assert MARKDOWN_SENTINEL in m_body.decode("utf-8")


def test_set_scenario_does_not_reset_evidence(origin):
    get(origin.port, accept=HTML_ACCEPT)
    assert origin.counter_snapshot().total_requests == 1
    origin.set_scenario("markdown_404")
    assert origin.scenario_id == "markdown_404"
    assert origin.counter_snapshot().total_requests == 1
    assert get(origin.port, accept=MARKDOWN_ACCEPT)[0] == 404
    assert origin.counter_snapshot().total_requests == 2
    assert len(origin.event_log()) == 2


def test_accept_quality_values_pick_highest_q(origin):
    status, _, body = get(
        origin.port, accept="text/html;q=0.1, text/markdown;q=0.9"
    )
    assert status == 200
    assert MARKDOWN_SENTINEL in body.decode("utf-8")


@pytest.mark.parametrize(
    "accept",
    [
        "text/markdown;q=0",
        "text/html;q=0",
        "text/html;q=0, text/markdown;q=0",
    ],
)
def test_accept_q_zero_returns_406_t014(origin, accept):
    """T014 (T003 P2-01): q=0 means "not acceptable" (RFC 9110
    §12.5.1) — a live origin must answer 406, not 200."""
    assert get(origin.port, accept=accept)[0] == 406


def test_accept_q_zero_loses_to_positive_q_t014(origin):
    status, _, body = get(
        origin.port, accept="text/html;q=0, text/markdown;q=0.5"
    )
    assert status == 200
    assert MARKDOWN_SENTINEL in body.decode("utf-8")
    status, _, body = get(
        origin.port, accept="text/html;q=0.5, text/markdown;q=0"
    )
    assert status == 200
    assert HTML_SENTINEL in body.decode("utf-8")


@pytest.mark.parametrize(
    ("accept", "sentinel"),
    [
        ("text/html;q=0.9, text/markdown;q=0.9", HTML_SENTINEL),
        ("text/markdown;q=0.9, text/html;q=0.9", MARKDOWN_SENTINEL),
        ("text/html;q=0.5, text/markdown;q=0.5", HTML_SENTINEL),
        ("text/markdown;q=0.5, text/html;q=0.5", MARKDOWN_SENTINEL),
    ],
)
def test_accept_q_tie_goes_to_first_listed_t014(origin, accept, sentinel):
    """T014 (T003 P2-02): a q-value tie goes to the first listed
    media type (documented _parse_accept rule, previously untested)."""
    status, _, body = get(origin.port, accept=accept)
    assert status == 200
    assert sentinel in body.decode("utf-8")


# ---------------------------------------------------------------------------
# T008 extended-Golden origin shapes (PROJECT_BOOK §11.3 E01–E03, E07–E11)
# ---------------------------------------------------------------------------


def test_vary_multi_fixture_serves_two_field_vary():
    server = SyntheticOrigin(port=0, scenario="vary_multi")
    server.start()
    try:
        _, h_headers, _ = get(server.port, accept=HTML_ACCEPT)
        _, m_headers, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_headers["vary"] == "Accept, Accept-Encoding"
    assert m_headers["vary"] == "Accept, Accept-Encoding"


def test_vary_star_fixture_serves_vary_star():
    server = SyntheticOrigin(port=0, scenario="vary_star")
    server.start()
    try:
        _, h_headers, _ = get(server.port, accept=HTML_ACCEPT)
        _, m_headers, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_headers["vary"] == "*"
    assert m_headers["vary"] == "*"


def test_vary_lowercase_field_name_on_the_wire():
    # E01: the Vary field NAME is lowercase on the wire. The `get`
    # helper lowercases header names, so this test reads the raw
    # header list, where http.client preserves the case as sent.
    server = SyntheticOrigin(port=0, scenario="vary_lowercase")
    server.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        try:
            conn.request("GET", "/doc", headers={"Accept": HTML_ACCEPT})
            resp = conn.getresponse()
            resp.read()
            names = [name for name, _ in resp.getheaders()]
        finally:
            conn.close()
    finally:
        server.stop()
    assert "vary" in names
    assert "Vary" not in names


def test_cache_control_fixtures_emit_directives():
    for scenario, directive in (
        ("cache_max_age_0", "max-age=0"),
        ("cache_no_cache", "no-cache"),
    ):
        server = SyntheticOrigin(port=0, scenario=scenario)
        server.start()
        try:
            _, h_headers, _ = get(server.port, accept=HTML_ACCEPT)
            _, m_headers, _ = get(server.port, accept=MARKDOWN_ACCEPT)
        finally:
            server.stop()
        assert h_headers["cache-control"] == directive
        assert m_headers["cache-control"] == directive


def test_markdown_406_fixture():
    server = SyntheticOrigin(port=0, scenario="markdown_406")
    server.start()
    try:
        h_status, _, _ = get(server.port, accept=HTML_ACCEPT)
        m_status, m_headers, m_body = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_status == 200
    assert m_status == 406
    assert m_headers["content-type"] == "text/plain; charset=utf-8"
    assert MARKDOWN_SENTINEL in m_body.decode("utf-8")


def test_html_markdown_content_type_fixture():
    server = SyntheticOrigin(port=0, scenario="html_markdown_content_type")
    server.start()
    try:
        h_status, h_headers, h_body = get(server.port, accept=HTML_ACCEPT)
        m_status, _, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_status == 200
    assert h_headers["content-type"] == "text/markdown; charset=utf-8"
    assert HTML_SENTINEL in h_body.decode("utf-8")
    assert m_status == 200


def test_scenario_with_unknown_vary_value_is_rejected(tmp_path):
    bad = {
        "scenario_id": "bad-vary",
        "representations": {
            "html": {"status": 200, "vary": "Accept-Language"},
            "markdown": {"status": 200},
        },
    }
    path = tmp_path / "bad-vary.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario(path)
```

## tests/integration/test_report_ui.py

- SHA-256：`7218698c157f872d12733816e4e7cfe64d38e61d7e67593e3349427e467c187d`
- 字节数：19692

```
"""Integration tests for the self-contained HTML report (P032 T010).

Acceptance criteria (IMPLEMENTATION_PLAN T010):

1. Opens offline, self-contained, no remote request.
2. All five verdicts display correctly.
3. The 48-scenario summary displays correctly.
4. No body text leaks (only hashes and match flags).
5. HTML export matches the JSON report field by field.

The tests assert on the generated static HTML (embedded JSON
payloads, section markers, remote-reference scans) and, when a
headless Chromium is available in the environment, on the actually
rendered DOM. No test re-runs an experiment: the 48 pages are
built from the existing T009 report samples.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "evidence" / "Reports"
GOLDEN_DIR = ROOT / "evidence" / "Golden"
REPORT_UI_DIR = ROOT / "report-ui"
EMBED_SCRIPT = ROOT / "scripts" / "embed_report.py"

SENTINELS = ("AT_HTML_SENTINEL_001", "AT_MARKDOWN_SENTINEL_001")
VERDICTS = (
    "PASS_OBSERVED",
    "ORIGIN_NEGOTIATION_ERROR",
    "REPRESENTATION_BLEED",
    "CONTRACT_MISMATCH",
    "INCONCLUSIVE",
)
SECTION_IDS = (
    "section-verdict",
    "section-baseline",
    "section-experiments",
    "section-timeline",
    "section-cache",
    "section-first-error",
    "section-diagnostics",
    "section-oracle",
    "section-hash",
    "section-privacy",
)
EXPECTED_DISTRIBUTION = {
    "PASS_OBSERVED": 16,
    "ORIGIN_NEGOTIATION_ERROR": 7,
    "REPRESENTATION_BLEED": 8,
    "CONTRACT_MISMATCH": 4,
    "INCONCLUSIVE": 13,
}

# One sample per verdict (T009 distribution 16/7/8/4/13).
VERDICT_SAMPLES = {
    "PASS_OBSERVED": "C01",
    "ORIGIN_NEGOTIATION_ERROR": "C07",
    "REPRESENTATION_BLEED": "C11",
    "CONTRACT_MISMATCH": "C19",
    "INCONCLUSIVE": "C20",
}


def run_embed(*argv: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EMBED_SCRIPT), *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def extract_payload(html: str, payload_id: str) -> object:
    match = re.search(
        rf'<script type="application/json" id="{payload_id}">\s*(.*?)\s*</script>',
        html,
        re.DOTALL,
    )
    assert match is not None, f"payload {payload_id} missing from HTML"
    return json.loads(match.group(1))


def assert_no_remote_references(html: str, *, allow_relative_links: bool) -> None:
    for sentinel in SENTINELS:
        assert sentinel not in html, f"Sentinel literal {sentinel} leaked into HTML"
    assert "<link" not in html
    assert "<iframe" not in html
    assert "<img" not in html
    assert "<script src" not in html
    assert html.count("<script") == 4, "expected exactly 4 inline <script> tags"
    assert "@import" not in html
    assert "url(" not in html
    assert "data:" not in html
    for match in re.finditer(r"https?://([^\s\"'<>/:]+)", html):
        host = match.group(1).strip("[]").lower()
        is_loopback = host == "localhost" or host == "::1" or (
            host.startswith("127.")
            and len(host.split(".")) == 4
            and all(part.isdigit() for part in host.split("."))
        )
        assert is_loopback, f"non-loopback URL in HTML: {match.group(0)}"
    hrefs = re.findall(r'href="([^"]*)"', html)
    if not allow_relative_links:
        assert hrefs == [], f"single-report page must have no links, got {hrefs}"
    else:
        for href in hrefs:
            assert re.fullmatch(r"[A-Za-z0-9_.\-]+\.html", href), f"non-relative href: {href}"


def load_report(sid: str) -> dict:
    return json.loads((REPORTS_DIR / f"{sid}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Single-report generation
# ---------------------------------------------------------------------------


def test_embed_single_report_round_trips_json(tmp_path: Path) -> None:
    out = tmp_path / "C11.html"
    result = run_embed(
        "evidence/Reports/C11.json",
        "--contract",
        "evidence/Golden/C11/contract.json",
        "-o",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    assert "PRIVACY PREVIEW" in result.stdout
    assert result.stdout.index("PRIVACY PREVIEW") < result.stdout.index("WROTE")
    html = out.read_text(encoding="utf-8")
    source = load_report("C11")
    assert extract_payload(html, "accepttwin-report") == source
    baseline = extract_payload(html, "accepttwin-baseline")
    assert baseline == {
        "html": {
            "accept": "text/html",
            "expected_status": 200,
            "expected_content_type": "text/html; charset=utf-8",
        },
        "markdown": {
            "accept": "text/markdown",
            "expected_status": 200,
            "expected_content_type": "text/markdown; charset=utf-8",
        },
    }
    for section_id in SECTION_IDS:
        assert f'id="{section_id}"' in html, f"missing section {section_id}"
    assert_no_remote_references(html, allow_relative_links=False)


def test_embed_without_contract_uses_frozen_baseline(tmp_path: Path) -> None:
    out = tmp_path / "C01.html"
    result = run_embed("evidence/Reports/C01.json", "-o", str(out))
    assert result.returncode == 0, result.stderr
    html = out.read_text(encoding="utf-8")
    baseline = extract_payload(html, "accepttwin-baseline")
    assert baseline["html"]["accept"] == "text/html"
    assert baseline["markdown"]["accept"] == "text/markdown"
    assert extract_payload(html, "accepttwin-report") == load_report("C01")


def test_embed_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.html"
    second = tmp_path / "second.html"
    for out in (first, second):
        result = run_embed(
            "evidence/Reports/C11.json",
            "--contract",
            "evidence/Golden/C11/contract.json",
            "-o",
            str(out),
        )
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes()


def test_check_only_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "C11.html"
    result = run_embed(
        "evidence/Reports/C11.json", "-o", str(out), "--check-only"
    )
    assert result.returncode == 0, result.stderr
    assert "PRIVACY PREVIEW" in result.stdout
    assert "CHECK ONLY" in result.stdout
    assert not out.exists()


# ---------------------------------------------------------------------------
# Five verdicts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verdict,sid", sorted(VERDICT_SAMPLES.items()))
def test_all_five_verdicts_display(tmp_path: Path, verdict: str, sid: str) -> None:
    out = tmp_path / f"{sid}.html"
    result = run_embed(f"evidence/Reports/{sid}.json", "-o", str(out))
    assert result.returncode == 0, result.stderr
    html = out.read_text(encoding="utf-8")
    verdict_section = re.search(
        r'<section id="section-verdict">.*?</section>', html, re.DOTALL
    )
    assert verdict_section is not None
    # The verdict badge is static in the template only after JS
    # rendering; the payload is the source of truth here, and the
    # rendered-DOM test below checks the badge text itself.
    payload = extract_payload(html, "accepttwin-report")
    assert payload["verdict"] == verdict
    assert payload["scenario_id"] == sid
    assert payload["report_hash"] in html
    # The verdict badge text itself is produced at runtime by the
    # compiled bundle (rendered-DOM test below checks it); the
    # payload must carry the exact verdict string.
    assert verdict in html


# ---------------------------------------------------------------------------
# HTML <-> JSON consistency (spot check: one bleed + one pass sample)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", ["C11", "C01"])
def test_html_matches_json_report(tmp_path: Path, sid: str) -> None:
    out = tmp_path / f"{sid}.html"
    result = run_embed(
        f"evidence/Reports/{sid}.json",
        "--contract",
        f"evidence/Golden/{sid}/contract.json",
        "-o",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    html = out.read_text(encoding="utf-8")
    payload = extract_payload(html, "accepttwin-report")
    source = load_report(sid)
    for field in (
        "verdict",
        "first_error",
        "first_error_experiment_id",
        "report_hash",
        "oracle",
        "oracle_parity",
        "final",
        "critical_count",
        "warning_count",
    ):
        assert payload[field] == source[field], f"{sid}: {field} mismatch"
    assert payload["diagnostics"] == source["diagnostics"]
    assert payload["observations"] == source["observations"]
    assert payload["input"] == source["input"]
    assert payload["reasons"] == source["reasons"]


# ---------------------------------------------------------------------------
# Fail-closed rejection
# ---------------------------------------------------------------------------


def test_embed_rejects_tampered_hash(tmp_path: Path) -> None:
    bad = load_report("C11")
    bad["report_hash"] = "0" * 64
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = run_embed(str(bad_path), "-o", str(tmp_path / "bad.html"))
    assert result.returncode == 1
    assert "EMBED_FAIL" in result.stderr
    assert not (tmp_path / "bad.html").exists()


def test_embed_rejects_forbidden_body_key(tmp_path: Path) -> None:
    bad = load_report("C01")
    bad["diagnostics"] = [
        {
            "code": "CONTRACT_MISMATCH",
            "severity": "CRITICAL",
            "message": "x",
            "experiment_id": "ORIGIN_HTML",
            "request_index": 1,
            "evidence": {"body": "leaked text"},
        }
    ]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = run_embed(str(bad_path), "-o", str(tmp_path / "bad.html"))
    assert result.returncode == 1
    assert "EMBED_FAIL" in result.stderr
    assert not (tmp_path / "bad.html").exists()


def test_embed_rejects_sentinel_literal(tmp_path: Path) -> None:
    bad = load_report("C01")
    bad["reasons"] = ["contains AT_HTML_SENTINEL_001 verbatim"]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = run_embed(str(bad_path), "-o", str(tmp_path / "bad.html"))
    assert result.returncode == 1
    assert "EMBED_FAIL" in result.stderr
    assert not (tmp_path / "bad.html").exists()


def test_embed_rejects_missing_file(tmp_path: Path) -> None:
    result = run_embed("evidence/Reports/ZZZ.json", "-o", str(tmp_path / "x.html"))
    assert result.returncode == 1
    assert "EMBED_FAIL" in result.stderr


# ---------------------------------------------------------------------------
# 48-scenario summary
# ---------------------------------------------------------------------------


def test_all_48_summary_matches_reports_and_record(tmp_path: Path) -> None:
    out_dir = tmp_path / "html"
    result = run_embed("--all-48", "--out-dir", str(out_dir))
    assert result.returncode == 0, result.stderr
    assert "PRIVACY PREVIEW" in result.stdout
    files = sorted(p.name for p in out_dir.iterdir())
    assert files == [f"{sid}.html" for sid in
                     [f"C{i:02d}" for i in range(1, 25)] + [f"E{i:02d}" for i in range(1, 25)]] + ["index.html"]
    summary = extract_payload(
        (out_dir / "index.html").read_text(encoding="utf-8"),
        "accepttwin-summary",
    )
    assert summary["total"] == 48
    assert summary["counts"] == EXPECTED_DISTRIBUTION
    recorded = json.loads((REPORTS_DIR / "REPORTS_SUMMARY.json").read_text(encoding="utf-8"))
    assert len(summary["rows"]) == 48
    for row in summary["rows"]:
        sid = row["scenario_id"]
        source = load_report(sid)
        assert row["verdict"] == source["verdict"] == recorded["samples"][sid]["verdict"]
        assert row["first_error"] == source["first_error"] == recorded["samples"][sid]["first_error"]
        assert row["oracle_parity"] == source["oracle_parity"] is True
        assert row["final"] is True
        assert row["report_hash"] == source["report_hash"] == recorded["samples"][sid]["report_hash"]
        assert row["critical_count"] == source["critical_count"]
        assert row["warning_count"] == source["warning_count"]
        page = (out_dir / f"{sid}.html").read_text(encoding="utf-8")
        assert extract_payload(page, "accepttwin-report") == source
        assert_no_remote_references(page, allow_relative_links=False)
    index_html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert_no_remote_references(index_html, allow_relative_links=True)
    # The per-scenario links are built at runtime by the bundle
    # from the summary payload (the rendered-DOM test below checks
    # href="C11.html" appears); the static file carries the data,
    # not the links.
    assert {row["scenario_id"] for row in summary["rows"]} == {
        f"C{i:02d}" for i in range(1, 25)
    } | {f"E{i:02d}" for i in range(1, 25)}


def test_no_sentinel_or_remote_in_committed_pages() -> None:
    html_dir = REPORTS_DIR / "html"
    assert html_dir.is_dir(), "evidence/Reports/html/ was not generated — run scripts/embed_report.py --all-48"
    pages = sorted(html_dir.glob("*.html"))
    assert len(pages) == 49
    for page in pages:
        html = page.read_text(encoding="utf-8")
        allow_links = page.name == "index.html"
        assert_no_remote_references(html, allow_relative_links=allow_links)


# ---------------------------------------------------------------------------
# Template and bundle hygiene
# ---------------------------------------------------------------------------


def test_template_and_assets_have_no_remote_references() -> None:
    for name in ("index.html", "styles.css", "report-ui.js"):
        text = (REPORT_UI_DIR / name).read_text(encoding="utf-8")
        for sentinel in SENTINELS:
            assert sentinel not in text, f"{name} contains a Sentinel literal"
        assert "http://" not in text, f"{name} contains http://"
        assert "https://" not in text, f"{name} contains https://"
        assert "@import" not in text, f"{name} contains @import"
        assert "url(" not in text, f"{name} contains url("
    template = (REPORT_UI_DIR / "index.html").read_text(encoding="utf-8")
    assert "未嵌入报告数据" in template
    for section_id in SECTION_IDS:
        assert f'id="{section_id}"' in template


def test_compiled_bundle_matches_typescript_sources() -> None:
    bundle = REPORT_UI_DIR / "report-ui.js"
    assert bundle.is_file()
    text = bundle.read_text(encoding="utf-8")
    assert "AcceptTwinUI.init();" in text
    assert "双向缓存时间线" in text
    assert "下载 JSON 报告" in text
    tsc = REPORT_UI_DIR / "node_modules" / ".bin" / "tsc"
    if tsc.is_file():
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = subprocess.run(
                [str(tsc), "-p", "tsconfig.json", "--outFile", str(tmp_path / "fresh.js")],
                cwd=REPORT_UI_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert result.returncode == 0, result.stderr
            fresh = (tmp_path / "fresh.js").read_text(encoding="utf-8")
            assert fresh == text, "committed report-ui.js is stale — run npm run build in report-ui/"
    else:
        # No local tsc: the marker assertions above still pin the
        # bundle content; a fresh recompile is verified in the T010
        # acceptance run (see report-ui/T010_NOTES.md).
        assert "AcceptTwinUI" in text


# ---------------------------------------------------------------------------
# Rendered DOM (headless Chromium, when available in the environment)
# ---------------------------------------------------------------------------


def _find_chrome() -> str | None:
    for candidate in (
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("google-chrome"),
        str(Path.home() / ".cache" / "ms-playwright" / "chromium-1255" / "chrome-linux64" / "chrome"),
        "/opt/meta-chromium/chrome",
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _dump_dom(chrome: str, html_path: Path, tmp_path: Path) -> str:
    out = tmp_path / (html_path.stem + ".dom.html")
    result = subprocess.run(
        [
            chrome,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--virtual-time-budget=5000",
            "--dump-dom",
            f"file://{html_path}",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[:500]
    out.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def test_headless_chrome_renders_report_offline(tmp_path: Path) -> None:
    chrome = _find_chrome()
    if chrome is None:
        # T014 (T010 P2-2): fail hard instead of silently skipping —
        # these are offline acceptance tests, and a Chromium-less
        # environment must not silently drop them. CI must provide a
        # headless Chromium (this repo's _find_chrome covers the
        # Playwright chromium-1255 install).
        pytest.fail(
            "headless Chromium is required for this offline rendering "
            "acceptance test, but none was found"
        )
    page = tmp_path / "C11.html"
    result = run_embed(
        "evidence/Reports/C11.json",
        "--contract",
        "evidence/Golden/C11/contract.json",
        "-o",
        str(page),
    )
    assert result.returncode == 0, result.stderr
    dom = _dump_dom(chrome, page, tmp_path)
    assert "REPRESENTATION_BLEED · 表示串版" in dom
    assert "请求 006" in dom
    assert "下载 JSON 报告（C11.json）" in dom
    assert "双重证据一致" in dom
    for section_id in SECTION_IDS:
        match = re.search(
            rf'<section id="{section_id}">(.*?)</section>', dom, re.DOTALL
        )
        assert match is not None, f"missing section {section_id} in rendered DOM"
        assert len(match.group(1).strip()) > 50, f"section {section_id} rendered empty"
    assert 'id="no-payload" hidden=""' in dom


def test_headless_chrome_renders_summary_offline(tmp_path: Path) -> None:
    chrome = _find_chrome()
    if chrome is None:
        # T014 (T010 P2-2): fail hard instead of silently skipping —
        # these are offline acceptance tests, and a Chromium-less
        # environment must not silently drop them. CI must provide a
        # headless Chromium (this repo's _find_chrome covers the
        # Playwright chromium-1255 install).
        pytest.fail(
            "headless Chromium is required for this offline rendering "
            "acceptance test, but none was found"
        )
    out_dir = tmp_path / "html"
    result = run_embed("--all-48", "--out-dir", str(out_dir))
    assert result.returncode == 0, result.stderr
    dom = _dump_dom(chrome, out_dir / "index.html", tmp_path)
    assert "48 场景汇总" in dom
    assert "PASS_OBSERVED 16" in dom
    assert "INCONCLUSIVE 13" in dom
    assert dom.count("<tr>") >= 49  # header + 48 rows
    assert 'href="C11.html"' in dom
```

## tests/performance/test_cli.py

- SHA-256：`bf89902212f89019ac42c03ee6b597994bb480d3805b7c5acc507b615d1c1dff`
- 字节数：3615

```
"""CLI tests (P032 T012): ``python -m accepttwin`` help + entry points.

Full ``verify``/``benchmark`` runs are NOT executed here: each one
re-runs all 48 live scenarios (plus repeat-100) and takes minutes;
they are the acceptance commands themselves, run by the T012
delivery and recorded under ``evidence/Performance/``. These tests
pin the cheap, deterministic surface: help text, argument errors,
and that both subcommands delegate to the reviewed implementations.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "accepttwin", *argv],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=60,
    )


def test_help_lists_verify_and_benchmark() -> None:
    proc = _run_cli("--help")
    assert proc.returncode == 0, proc.stderr
    assert "verify" in proc.stdout
    assert "benchmark" in proc.stdout
    assert "accepttwin" in proc.stdout


def test_verify_help_names_suites() -> None:
    proc = _run_cli("verify", "--help")
    assert proc.returncode == 0, proc.stderr
    assert "--suite" in proc.stdout
    assert "s0" in proc.stdout and "all" in proc.stdout


def test_benchmark_help_names_suite_all() -> None:
    proc = _run_cli("benchmark", "--help")
    assert proc.returncode == 0, proc.stderr
    assert "--suite" in proc.stdout
    assert "all" in proc.stdout


def test_no_subcommand_exits_2_and_prints_help() -> None:
    proc = _run_cli()
    assert proc.returncode == 2
    assert "verify" in proc.stdout and "benchmark" in proc.stdout


def test_unknown_suite_exits_2() -> None:
    proc = _run_cli("verify", "--suite", "bogus")
    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


def test_unknown_subcommand_exits_2() -> None:
    proc = _run_cli("frobnicate")
    assert proc.returncode == 2


def test_version_reports_frozen_version() -> None:
    proc = _run_cli("--version")
    assert proc.returncode == 0, proc.stderr
    assert "1.0.0" in proc.stdout


def test_documented_acceptance_commands_match_help() -> None:
    """README/USAGE must quote the acceptance commands exactly as
    the CLI spells them (T012 acceptance: docs == --help)."""
    help_text = _run_cli("--help").stdout
    assert "verify" in help_text and "benchmark" in help_text
    for doc in (ROOT / "README.md", ROOT / "docs" / "USAGE.md"):
        text = doc.read_text(encoding="utf-8")
        assert "python -m accepttwin verify --suite all" in text
        assert "python -m accepttwin benchmark --suite all" in text
        assert "python -m accepttwin verify --suite s0" in text


def test_verify_and_benchmark_delegate_to_reviewed_runners() -> None:
    """The CLI calls the reviewed script entry points; it does not
    contain a second Golden runner, classifier or report builder."""
    from accepttwin.cli import cmd_benchmark, cmd_verify, main

    assert callable(main) and callable(cmd_verify) and callable(cmd_benchmark)
    source = Path(__import__("accepttwin.cli", fromlist=["cli"]).__file__).read_text(
        encoding="utf-8"
    )
    assert "run_all_48" in source and "run_s0" in source
    assert "def classify_run" not in source
    assert "def build_report" not in source
    assert "def run_experiments" not in source
    assert "def canonical_json_bytes" not in source
    # The only canonical-JSON use is the import of the single source.
    assert "from accepttwin.contract import canonical_json_bytes" in source
```

## tests/performance/test_performance.py

- SHA-256：`f42af1698174df0125f6a1d97eb8f21ca48261d7254638cc9f991922385a5c54`
- 字节数：3425

```
"""Performance + determinism tests (P032 T012, §10.4/§10.5, §18 AC10/AC11).

Every test here executes real local HTTP (fresh origin + proxy pair
per scenario, via ``s0_harness.run_scenario``) — no cached report is
ever read for a timing or a hash. The full 100-run check lives in
``python -m accepttwin benchmark --suite all`` (and in
``scripts/run_s0.py``); these tests pin the same mechanism at small
scale so the suite stays fast.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from accepttwin.contract import canonical_json_bytes  # noqa: E402
from s0_harness import load_scenario, run_scenario  # noqa: E402

FORBIDDEN = (
    b"generated_at",
    b"duration_ms",
    b"process_id",
    b"temporary_path",
    b"ephemeral_port",
    b"timestamp",
    b"uuid",
    b"random",
)


@pytest.mark.parametrize("scenario_id", ["C01", "C11", "E13"])
def test_single_scenario_four_experiments_under_one_second(scenario_id: str) -> None:
    fixture_dir = ROOT / "fixtures" / (
        "s0" if scenario_id.startswith("C") else "extended"
    )
    fixture = load_scenario(scenario_id, fixture_dir)
    outcome = run_scenario(
        scenario_id,
        fixture_dir=fixture_dir,
        contract_prefix="s0" if scenario_id.startswith("C") else "ext",
    )
    # 8 real HTTP requests: 2 direct-origin baselines + 6 proxied
    # (2 cold + 2 x 2 warm). §10.5: report generation is excluded
    # from this duration; duration_seconds covers run_experiments.
    assert len(outcome.run.observations) == 8
    assert len(outcome.run.reset_evidence) == 4
    assert outcome.duration_seconds < 1.0, (
        f"{scenario_id} took {outcome.duration_seconds:.3f}s, limit 1.0s"
    )
    assert outcome.production.verdict == fixture["expected_verdict"]
    assert outcome.production.first_error == fixture["expected_first_error"]


def test_canonical_json_has_no_nondeterministic_fields() -> None:
    outcome = run_scenario("C01")
    raw = canonical_json_bytes(outcome.report)
    for needle in FORBIDDEN:
        assert needle not in raw, f"canonical JSON contains {needle!r}"
    assert hashlib.sha256(raw).hexdigest() == outcome.report_hash


def test_repeat_three_fresh_pairs_same_hash() -> None:
    """Small-scale form of the repeat-100 gate: fresh pair (fresh
    OS-assigned ports) per run, real experiments every time."""
    hashes = set()
    for i in range(3):
        outcome = run_scenario("C01", namespace_prefix=f"perf-repeat-{i + 1}")
        assert outcome.production.verdict == "PASS_OBSERVED"
        hashes.add(outcome.report_hash)
    assert len(hashes) == 1


def test_run_ignores_environment_proxies() -> None:
    """With every proxy variable pointed at a dead proxy, a live
    scenario still passes: the product never reads the environment
    proxy (§0.2 item 7, §17.4 item 5)."""
    for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ[var] = "http://127.0.0.1:1"
    try:
        outcome = run_scenario("C01")
    finally:
        for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            os.environ.pop(var, None)
    assert outcome.production.verdict == "PASS_OBSERVED"
    assert outcome.duration_seconds < 1.0
```

## tests/privacy/test_body_limit.py

- SHA-256：`7bbe0d4d97f7b38858664fc150a5aac465a05b6d93fcb63deab52d189c99c580`
- 字节数：16587

```
"""Privacy regression: 1 MiB body cap (P032 T011, scenario 8).

Acceptance scenario 8 — oversize body rejected (PROJECT_BOOK §17.4
item 8; ``limits.max_body_bytes`` defaults to 1 MiB).

Verified at three levels:

1. unit: :func:`accepttwin.privacy.check_body_size` /
   :func:`accepttwin.privacy.enforce_body_limit` enforce the cap on
   measured sizes and raw bytes, with exact boundary behaviour;
2. classifier: a fabricated oversize observation is rejected by the
   production classifier with ``INCONCLUSIVE_LIMIT`` (the same path
   the E21 Golden exercises live);
3. live: the E21-style oversize run is re-run here through the real
   runner and the privacy angle is asserted — the oversize body is
   measured (``body_size`` recorded, hash recorded) but never stored
   as text anywhere in the run's evidence.

Deliberate boundary (recorded, not hidden): the cap is enforced on
the *measured* body at classification time, and since T014 the
socket read itself is bounded too — ``_http_get`` /
``_fetch_origin`` retain at most ``limit + 1`` bytes via
:func:`accepttwin.privacy.read_http_body_bounded`, while the exact
total size, whole-stream SHA-256 and Sentinel presence are still
measured over the full stream (see F-01 in
evidence/Privacy/PRIVACY_REPORT.md, closed by T014).
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from accepttwin.classifier import classify_run
from accepttwin.contract import parse_contract
from accepttwin.evidence import RequestObservation
from accepttwin.privacy import (
    MAX_BODY_BYTES,
    PrivacyError,
    check_body_size,
    enforce_body_limit,
    read_http_body_bounded,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"


# ---------------------------------------------------------------------------
# Level 1 — unit: the cap itself, including exact boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "size",
    [0, 1, 1024, MAX_BODY_BYTES - 1, MAX_BODY_BYTES],
)
def test_body_size_at_or_below_cap_accepted(size):
    assert check_body_size(size) == size
    assert enforce_body_limit(b"x" * size) == b"x" * size


@pytest.mark.parametrize(
    "size",
    [MAX_BODY_BYTES + 1, MAX_BODY_BYTES + 1024, 2 * MAX_BODY_BYTES],
)
def test_body_size_above_cap_rejected(size):
    with pytest.raises(PrivacyError, match="exceeds the 1048576 byte limit"):
        check_body_size(size)
    with pytest.raises(PrivacyError, match="exceeds the 1048576 byte limit"):
        enforce_body_limit(b"x" * size)


def test_negative_body_size_rejected():
    with pytest.raises(PrivacyError, match="must not be negative"):
        check_body_size(-1)


def test_non_integer_body_size_rejected():
    with pytest.raises(PrivacyError, match="must be an integer"):
        check_body_size(1.5)
        check_body_size("1048576")


def test_custom_limit_is_honoured():
    assert check_body_size(100, limit=100) == 100
    with pytest.raises(PrivacyError):
        check_body_size(101, limit=100)


def test_enforce_body_limit_rejects_non_bytes():
    with pytest.raises(PrivacyError, match="must be bytes"):
        enforce_body_limit("not bytes")


def test_cap_constant_is_1_mib():
    assert MAX_BODY_BYTES == 1_048_576


# ---------------------------------------------------------------------------
# Level 1b — bounded read: exact measurement, bounded retention (T014)
# ---------------------------------------------------------------------------


def test_bounded_read_returns_small_body_whole_with_exact_hash():
    body = b"<html>AT_HTML_SENTINEL_001</html>"
    retained, total, digest, match = read_http_body_bounded(
        io.BytesIO(body), 1024, sentinel=b"AT_HTML_SENTINEL_001"
    )
    assert retained == body
    assert total == len(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert match is True


def test_bounded_read_oversize_retains_limit_plus_one_but_measures_exact():
    # 2 MiB stream, limit 1 MiB: only 1 MiB + 1 bytes are retained,
    # but the reported size and hash are exact over the whole stream
    # (T011 F-01 / T013-F04: the old unbounded resp.read() returned
    # all 2 MiB).
    body = b"x" * (2 * MAX_BODY_BYTES)
    retained, total, digest, match = read_http_body_bounded(
        io.BytesIO(body), MAX_BODY_BYTES, sentinel=b"AT_HTML_SENTINEL_001"
    )
    assert len(retained) == MAX_BODY_BYTES + 1
    assert retained == body[: MAX_BODY_BYTES + 1]
    assert total == len(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert match is False


def test_bounded_read_finds_sentinel_past_the_retained_prefix():
    # Sentinel at offset 1.5 MiB — past the retained prefix — must
    # still be found: the scan covers the whole stream, not just the
    # retained bytes (a Sentinel straddling a 64 KiB chunk boundary
    # is covered by the overlap scan).
    sentinel = b"AT_HTML_SENTINEL_001"
    body = b"x" * (MAX_BODY_BYTES + 512) + sentinel + b"y" * 100
    retained, total, digest, match = read_http_body_bounded(
        io.BytesIO(body), MAX_BODY_BYTES, sentinel=sentinel
    )
    assert len(retained) == MAX_BODY_BYTES + 1
    assert sentinel not in retained
    assert total == len(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert match is True


def test_bounded_read_empty_body_and_negative_limit():
    retained, total, digest, match = read_http_body_bounded(
        io.BytesIO(b""), MAX_BODY_BYTES, sentinel=b"S"
    )
    assert (retained, total, digest, match) == (
        b"",
        0,
        hashlib.sha256(b"").hexdigest(),
        False,
    )
    with pytest.raises(PrivacyError):
        read_http_body_bounded(io.BytesIO(b"x"), -1)


# ---------------------------------------------------------------------------
# Level 2 — classifier: an oversize observation is rejected
# ---------------------------------------------------------------------------


def _healthy_observations(*, oversize_index=None):
    """Eight healthy observations; optionally make one oversize."""
    observations = []
    for index in range(1, 9):
        rep = "html" if index in (1, 3, 5, 8) else "markdown"
        experiment = {
            1: "ORIGIN_HTML",
            2: "ORIGIN_MARKDOWN",
            3: "HTML_COLD",
            4: "MARKDOWN_COLD",
            5: "HTML_TO_MARKDOWN",
            6: "HTML_TO_MARKDOWN",
            7: "MARKDOWN_TO_HTML",
            8: "MARKDOWN_TO_HTML",
        }[index]
        body = ("h" if rep == "html" else "m") * 64
        observations.append(
            RequestObservation(
                request_index=index,
                experiment_id=experiment,
                requested_representation=rep,
                response_status=200,
                response_content_type=(
                    "text/html; charset=utf-8"
                    if rep == "html"
                    else "text/markdown; charset=utf-8"
                ),
                body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                sentinel_match=True,
                cache_status=(
                    None if index <= 2 else "MISS"
                ),
                cache_key_sha256="k" * 64 if index > 2 else None,
                cache_entry_id=f"entry-{index:03d}" if index > 2 else None,
                origin_counter_before=index - 1,
                origin_counter_after=index,
                origin_counter_delta=1,
            )
        )
    return observations


def _classify_with_raw(observations, raw_observations):
    contract = parse_contract(
        json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    )
    from accepttwin.cache_proxy import ResetEvidence

    resets = [
        ResetEvidence(
            namespace=f"t011-{name}",
            success=True,
            entries_before=1,
            entries_after=0,
            entries_removed=1,
        )
        for name in (
            "html-cold",
            "markdown-cold",
            "html-to-markdown",
            "markdown-to-html",
        )
    ]
    # origin_events=None: ADR-002 route B — the unit-test caller declares
    # the origin cross-check is not performed (an empty list would mean
    # "checked and found nothing" and fail closed).
    return classify_run(
        contract, observations, None, resets, raw_observations=raw_observations
    )


def test_oversize_observation_rejected_by_classifier():
    """One oversize warm-cache body -> INCONCLUSIVE_LIMIT, not PASS."""
    from accepttwin.evidence import RawObservation

    observations = _healthy_observations()
    raws = []
    for obs in observations:
        oversize = obs.request_index == 6
        raws.append(
            RawObservation(
                request_index=obs.request_index,
                experiment_id=obs.experiment_id,
                requested_representation=obs.requested_representation,
                method="GET",
                url="http://127.0.0.1:18765/doc",
                accept=(
                    "text/html"
                    if obs.requested_representation == "html"
                    else "text/markdown"
                ),
                response_status=200,
                response_content_type=obs.response_content_type,
                body_sha256=obs.body_sha256,
                body_size=(
                    MAX_BODY_BYTES + 1 if oversize else 64
                ),
                sentinel_match=True,
                sentinel_sha256="s" * 64,
                response_headers={},
                cache_status_header="MISS" if obs.request_index > 2 else None,
                cache_key_sha256=obs.cache_key_sha256,
                cache_entry_id=obs.cache_entry_id,
                verified_cache_state=None,
                cache_verification_reasons=(),
                cache_entry_count_before=None,
                cache_entry_count_after=None,
                origin_counter_before=obs.origin_counter_before,
                origin_counter_after=obs.origin_counter_after,
                origin_counter_delta=1,
                origin_event_present=True,
                transport_error=None,
            )
        )
    result = _classify_with_raw(observations, raws)
    assert result.verdict == "INCONCLUSIVE"
    assert any(
        d.code == "INCONCLUSIVE_LIMIT" for d in result.diagnostics
    )


def test_healthy_observations_at_cap_pass_classifier():
    """Control: the same run with all bodies at 64 bytes passes."""
    observations = _healthy_observations()
    raws = []
    for obs in observations:
        from accepttwin.evidence import RawObservation

        raws.append(
            RawObservation(
                request_index=obs.request_index,
                experiment_id=obs.experiment_id,
                requested_representation=obs.requested_representation,
                method="GET",
                url="http://127.0.0.1:18765/doc",
                accept=(
                    "text/html"
                    if obs.requested_representation == "html"
                    else "text/markdown"
                ),
                response_status=200,
                response_content_type=obs.response_content_type,
                body_sha256=obs.body_sha256,
                body_size=64,
                sentinel_match=True,
                sentinel_sha256="s" * 64,
                response_headers={},
                cache_status_header="MISS" if obs.request_index > 2 else None,
                cache_key_sha256=obs.cache_key_sha256,
                cache_entry_id=obs.cache_entry_id,
                verified_cache_state=None,
                cache_verification_reasons=(),
                cache_entry_count_before=None,
                cache_entry_count_after=None,
                origin_counter_before=obs.origin_counter_before,
                origin_counter_after=obs.origin_counter_after,
                origin_counter_delta=1,
                origin_event_present=True,
                transport_error=None,
            )
        )
    result = _classify_with_raw(observations, raws)
    assert result.verdict == "PASS_OBSERVED"


# ---------------------------------------------------------------------------
# Level 3 — live: oversize bodies are measured, never stored as text
# ---------------------------------------------------------------------------


def test_live_oversize_run_measures_but_never_stores_body():
    """E21 live run: bodies > 1 MiB are flagged, not persisted.

    Reuses the frozen E21 fixture through the same harness the
    Golden suite uses (``scripts/s0_harness.py``) — real loopback
    HTTP, real runner, real classifier.
    """
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from s0_harness import EXTENDED_FIXTURE_DIR, run_scenario

    outcome = run_scenario(
        "E21",
        fixture_dir=EXTENDED_FIXTURE_DIR,
        contract_prefix="ext-t011",
        namespace_prefix="t011-E21-size",
    )
    assert outcome.production.verdict == "INCONCLUSIVE"
    assert any(
        d.code == "INCONCLUSIVE_LIMIT"
        for d in outcome.production.diagnostics
    )
    for raw in outcome.run.raw_observations[2:]:
        assert raw.body_size > MAX_BODY_BYTES
    for raw in outcome.run.raw_observations[:2]:
        assert raw.body_size <= MAX_BODY_BYTES
    # Nothing in the run's serialised evidence contains body text:
    # only hashes, sizes and match flags are recorded (§7.12 I-12).
    from accepttwin.privacy import find_forbidden_keys

    raw_dicts = [raw.as_dict() for raw in outcome.run.raw_observations]
    assert find_forbidden_keys(raw_dicts) == []
    blob = json.dumps(raw_dicts, ensure_ascii=False)
    assert "AT_HTML_SENTINEL_001" not in blob
    assert "AT_MARKDOWN_SENTINEL_001" not in blob
    assert all(raw.body_sha256 and len(raw.body_sha256) == 64 for raw in outcome.run.raw_observations)


# ---------------------------------------------------------------------------
# Level 3b — live: both production read sites are bounded (T014)
# ---------------------------------------------------------------------------


def _serve_bytes(body: bytes):
    """A throwaway loopback origin serving *body* for one test."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_live_http_get_bounds_retention_but_measures_exact():
    """T011 F-01: _http_get on a 2 MiB origin retains 1 MiB + 1 bytes.

    The old unbounded read returned all 2 MiB; the bounded read
    retains only the prefix while body_size / body_sha256 /
    sentinel_match stay exact over the whole stream.
    """
    from accepttwin.experiment_runner import _http_get

    sentinel = b"AT_HTML_SENTINEL_001"
    body = sentinel + b"x" * (2 * MAX_BODY_BYTES - len(sentinel))
    server = _serve_bytes(body)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/doc"
        result = _http_get(
            url, "html", 5.0, max_body=MAX_BODY_BYTES, sentinel=sentinel
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.status == 200
    assert len(result.body) == MAX_BODY_BYTES + 1
    assert result.body_size == len(body)
    assert result.body_sha256 == hashlib.sha256(body).hexdigest()
    assert result.sentinel_match is True


def test_live_proxy_fetch_bounds_retention():
    """T013-F04: proxy _fetch_origin on a 2 MiB origin is bounded too."""
    from accepttwin.cache_proxy import ControlledCacheProxy

    body = b"S" + b"x" * (2 * MAX_BODY_BYTES - 1)
    server = _serve_bytes(body)
    proxy = ControlledCacheProxy(
        port=0,
        mode="respect_vary",
        origin_url=f"http://127.0.0.1:{server.server_address[1]}/doc",
    )
    proxy.start()
    try:
        _, _, _, _, fetched = proxy._fetch_origin("/doc", "text/html")
    finally:
        proxy.stop()
        server.shutdown()
        server.server_close()
    assert len(fetched) == MAX_BODY_BYTES + 1
    assert fetched == body[: MAX_BODY_BYTES + 1]
```

## tests/privacy/test_cleanup_command.py

- SHA-256：`6a6e2aa94e17635127cfcf415aa3063a55c843e9fa4b2c4793ff90047c4715a0`
- 字节数：9177

```
"""Privacy regression: workspace-bounded cleanup (P032 T011).

Acceptance scenarios (IMPLEMENTATION_PLAN T011, PROJECT_BOOK §17.3):

12. the delete command can clean up specified files;
13. the cleanup command cannot delete arbitrary paths outside the
    workspace.

No cleanup command existed before T011 (``scripts/`` had none), so
this task implements the minimal one (§17): ``scripts/clean_evidence.py``
over :func:`accepttwin.privacy.delete_evidence_files`. Every refusal
is tested against a live "victim" file outside the workspace whose
survival is asserted afterwards — a refusal that still deleted the
file would be caught, not just reported.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from accepttwin.privacy import (
    PrivacyError,
    delete_evidence_files,
    resolve_cleanup_target,
)

ROOT = Path(__file__).resolve().parents[2]
CLEAN_SCRIPT = ROOT / "scripts" / "clean_evidence.py"


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Scenario 12 — the delete command can clean up specified files
# ---------------------------------------------------------------------------


def test_delete_named_files_inside_workspace(tmp_path):
    victim1 = _write(tmp_path / "evidence" / "tmp-a.json")
    victim2 = _write(tmp_path / "tmp-b.txt")
    keeper = _write(tmp_path / "keep.txt")
    deleted = delete_evidence_files(tmp_path, [victim1, victim2])
    assert deleted == [victim1.resolve(), victim2.resolve()]
    assert not victim1.exists()
    assert not victim2.exists()
    assert keeper.exists()


def test_delete_by_relative_path(tmp_path):
    target = _write(tmp_path / "sub" / "temp.html")
    deleted = delete_evidence_files(tmp_path, ["sub/temp.html"])
    assert deleted == [target.resolve()]
    assert not target.exists()


def test_delete_nested_path_with_dot_segments(tmp_path):
    target = _write(tmp_path / "a" / "b" / "temp.txt")
    deleted = delete_evidence_files(tmp_path, ["a/./b/../b/temp.txt"])
    assert deleted == [target.resolve()]
    assert not target.exists()


def test_dry_run_deletes_nothing(tmp_path):
    target = _write(tmp_path / "temp.txt")
    would_delete = delete_evidence_files(tmp_path, [target], dry_run=True)
    assert would_delete == [target.resolve()]
    assert target.exists()


def test_cli_deletes_named_file(tmp_path):
    target = _write(tmp_path / "evidence" / "old.json")
    result = _run_cli("--root", str(tmp_path), str(target))
    assert result.returncode == 0, result.stderr
    assert "deleted" in result.stdout
    assert not target.exists()


def test_cli_dry_run(tmp_path):
    target = _write(tmp_path / "evidence" / "temp.txt")
    result = _run_cli("--root", str(tmp_path), "--dry-run", str(target))
    assert result.returncode == 0, result.stderr
    assert "would delete" in result.stdout
    assert target.exists()


def test_cli_refuses_file_outside_evidence_subtree(tmp_path):
    """T014 (T011 P2): the script's deletable subtree is narrowed
    to evidence/ — an explicitly named file at the workspace root
    (e.g. a source file) is refused, even though it is inside the
    workspace and a regular file."""
    target = _write(tmp_path / "temp.txt")
    result = _run_cli("--root", str(tmp_path), str(target))
    assert result.returncode == 2
    assert "REFUSED" in result.stderr
    assert "outside the allowed subtree" in result.stderr
    assert target.exists()


def test_allowed_subtrees_parameter_narrows_primitive(tmp_path):
    """T014 (T011 P2): the primitive honours allowed_subtrees when
    a caller passes it; without it the workspace boundary stands."""
    inside = _write(tmp_path / "evidence" / "old.json")
    outside = _write(tmp_path / "src.txt")
    assert delete_evidence_files(
        tmp_path, [inside], allowed_subtrees=("evidence",)
    ) == [inside.resolve()]
    assert not inside.exists()
    with pytest.raises(PrivacyError, match="outside the allowed subtree"):
        delete_evidence_files(
            tmp_path, [outside], allowed_subtrees=("evidence",)
        )
    assert outside.exists()


def test_cli_defaults_root_to_project_root(tmp_path):
    """With no --root, the project root is used (refuses outside)."""
    outside = _write(tmp_path / "outside.txt")
    result = _run_cli(str(outside))
    assert result.returncode == 2
    assert "REFUSED" in result.stderr
    assert outside.exists()


# ---------------------------------------------------------------------------
# Scenario 13 — the cleanup command cannot delete outside the workspace
# ---------------------------------------------------------------------------


def test_absolute_path_outside_workspace_refused(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    with pytest.raises(PrivacyError, match="outside the workspace"):
        delete_evidence_files(workspace, [victim])
    assert victim.exists()
    assert victim.read_text() == "do not delete"


def test_dotdot_escape_refused(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    with pytest.raises(PrivacyError, match="outside the workspace"):
        delete_evidence_files(workspace, ["../victim.txt"])
    assert victim.exists()


def test_symlink_inside_pointing_outside_refused(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    link = workspace / "link.txt"
    link.symlink_to(victim)
    with pytest.raises(PrivacyError, match="symlink"):
        delete_evidence_files(workspace, [link])
    assert victim.exists()
    assert link.is_symlink()


def test_symlink_pointing_inside_is_still_refused(tmp_path):
    """Fail-closed: symlinks are never followed, even inward ones."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    real = _write(workspace / "real.txt")
    link = workspace / "link.txt"
    link.symlink_to(real)
    with pytest.raises(PrivacyError, match="symlink"):
        delete_evidence_files(workspace, [link])
    assert real.exists()


def test_workspace_root_itself_refused(tmp_path):
    with pytest.raises(PrivacyError):
        delete_evidence_files(tmp_path, [tmp_path])
    assert tmp_path.exists()


def test_directory_refused(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    _write(subdir / "file.txt")
    with pytest.raises(PrivacyError, match="not a regular file"):
        delete_evidence_files(tmp_path, [subdir])
    assert (subdir / "file.txt").exists()


def test_missing_file_refused(tmp_path):
    with pytest.raises(PrivacyError, match="does not exist"):
        delete_evidence_files(tmp_path, ["no-such-file.txt"])


def test_empty_target_list_refused(tmp_path):
    with pytest.raises(PrivacyError, match="no cleanup targets"):
        delete_evidence_files(tmp_path, [])


def test_one_bad_target_blocks_the_whole_batch(tmp_path):
    """Atomicity: a bad target means nothing is deleted at all."""
    good = _write(tmp_path / "good.txt")
    # A real file just outside the workspace, reached via a `..` escape.
    victim = _write(tmp_path.parent / "t011-victim-outside.txt", "keep me")
    try:
        with pytest.raises(PrivacyError):
            delete_evidence_files(tmp_path, [good, "../t011-victim-outside.txt"])
        assert good.exists()
        assert victim.exists()
    finally:
        victim.unlink(missing_ok=True)


def test_cli_refuses_outside_path_with_nonzero_exit(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    result = _run_cli("--root", str(workspace), str(victim))
    assert result.returncode == 2
    assert "REFUSED" in result.stderr
    assert "outside the workspace" in result.stderr
    assert victim.exists()


def test_cli_refuses_dotdot_escape(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    result = _run_cli("--root", str(workspace), "../victim.txt")
    assert result.returncode == 2
    assert victim.exists()


def test_cli_refuses_symlink(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    link = workspace / "link.txt"
    link.symlink_to(victim)
    result = _run_cli("--root", str(workspace), str(link))
    assert result.returncode == 2
    assert victim.exists()


def test_resolve_returns_canonical_absolute_path(tmp_path):
    target = _write(tmp_path / "sub" / "temp.txt")
    resolved = resolve_cleanup_target(tmp_path, "sub/temp.txt")
    assert resolved == target.resolve()
    assert resolved.is_absolute()
```

## tests/privacy/test_html_self_contained.py

- SHA-256：`0b0dfb52bd604727373dc36971a3c5cd7d9d54ec55648a77cf5ae744c0f078e7`
- 字节数：5714

```
"""Privacy regression: HTML reports are self-contained (P032 T011).

Acceptance scenario 11 — HTML does not access remote resources
(PROJECT_BOOK §14.4, §17.1; IMPLEMENTATION_PLAN T010/T011).

This test *pins* the result the T010 independent review already
verified by hand (49 pages, no remote references, no Sentinel
literals): it re-scans all 49 pages in ``evidence/Reports/html/``
with :mod:`accepttwin.privacy` on every run, so any later page that
gains a CDN link, a remote font, an image or a Sentinel literal
fails loudly. Positive cases (each forbidden construct, alone)
prove the scanner actually fires; negative cases (inline script,
relative link, loopback evidence URL) prove it does not over-fire.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from accepttwin.privacy import (
    PrivacyError,
    assert_html_directory_clean,
    scan_html_directory,
    scan_html_for_remote_resources,
)

ROOT = Path(__file__).resolve().parents[2]
HTML_DIR = ROOT / "evidence" / "Reports" / "html"


# ---------------------------------------------------------------------------
# The scanner fires on every forbidden construct (positive cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("snippet", "kind"),
    [
        ('<link rel="stylesheet" href="https://cdn.example.com/x.css">', "link-tag"),
        ('<link rel="stylesheet" href="local.css">', "link-tag"),
        ('<iframe src="https://example.com/"></iframe>', "iframe-tag"),
        ('<img src="https://example.com/pic.png">', "img-tag"),
        ('<img src="pic.png">', "img-tag"),
        ('<script src="https://cdn.example.com/app.js"></script>', "script-src"),
        ('<script src="app.js"></script>', "script-src"),
        ("<style>@import url('https://fonts.googleapis.com/css');</style>", "css-import"),
        ("<style>@import 'theme.css';</style>", "css-import"),
        ("<div style=\"background: url(https://example.com/bg.png)\"></div>", "css-url"),
        ("<div style=\"background: url(data:image/png;base64,AAAA)\"></div>", "css-url"),
        ('<a href="https://example.com/">out</a>', "remote-url"),
        ('<a href="http://example.com/">out</a>', "remote-url"),
        ('<img src="//cdn.example.com/pic.png">', "remote-url"),
        ('<p>see https://example.com/docs for details</p>', "remote-url"),
        ('<p>data:text/html,<b>x</b></p>', "data-uri"),
        ("<p>body contained AT_HTML_SENTINEL_001</p>", "sentinel-literal"),
        ("<p>body contained AT_MARKDOWN_SENTINEL_001</p>", "sentinel-literal"),
        ('<link href="https://fonts.googleapis.com/css2?family=X">', "link-tag"),
    ],
)
def test_scanner_fires_on_forbidden_construct(snippet, kind):
    refs = scan_html_for_remote_resources(snippet)
    assert any(ref.kind == kind for ref in refs), refs


# ---------------------------------------------------------------------------
# The scanner does not over-fire (negative cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "snippet",
    [
        "<script>document.getElementById('x').textContent = 'hi';</script>",
        '<a href="C11.html">C11</a>',
        '<a href="#section-verdict">jump</a>',
        # Loopback evidence URLs are diagnostic text (§8.6), not fetches.
        "<p>request_url: http://127.0.0.1:18765/doc</p>",
        "<p>redirect_target: http://localhost:18766/other</p>",
        "<p>redirect_target: http://[::1]:18766/other</p>",
        "<p>redirect_target: redacted:non-loopback</p>",
        "<p>body_sha256: ab12cd34 sentinel_match: true</p>",
        "<!DOCTYPE html><html><head><title>t</title></head><body></body></html>",
    ],
)
def test_scanner_passes_clean_html(snippet):
    assert scan_html_for_remote_resources(snippet) == []


# ---------------------------------------------------------------------------
# Scenario 11 — all 49 frozen pages are clean
# ---------------------------------------------------------------------------


def test_all_49_pages_scan_clean():
    """Pin of the T010 review finding: 49 pages, 0 violations."""
    result = assert_html_directory_clean(HTML_DIR, expected_count=49)
    assert len(result) == 49
    assert all(refs == [] for refs in result.values())
    expected_names = {f"C{i:02d}.html" for i in range(1, 25)}
    expected_names |= {f"E{i:02d}.html" for i in range(1, 25)}
    expected_names.add("index.html")
    assert set(result) == expected_names


def test_scan_directory_returns_per_file_results():
    result = scan_html_directory(HTML_DIR)
    assert len(result) == 49
    assert result["index.html"] == []
    assert result["C11.html"] == []


def test_scan_directory_rejects_missing_directory(tmp_path):
    with pytest.raises(PrivacyError, match="does not exist"):
        scan_html_directory(tmp_path / "no-such-dir")


def test_expected_count_mismatch_is_a_failure():
    with pytest.raises(PrivacyError, match="expected 48 HTML pages"):
        assert_html_directory_clean(HTML_DIR, expected_count=48)


def test_tainted_directory_fails(tmp_path):
    """Positive control: one bad page fails the whole directory."""
    good = tmp_path / "good.html"
    good.write_text("<html><body><script>var x = 1;</script></body></html>")
    bad = tmp_path / "bad.html"
    bad.write_text(
        '<html><body><img src="https://example.com/x.png"></body></html>'
    )
    result = scan_html_directory(tmp_path)
    assert result["good.html"] == []
    assert any(ref.kind == "img-tag" for ref in result["bad.html"])
    with pytest.raises(PrivacyError, match="bad.html"):
        assert_html_directory_clean(tmp_path, expected_count=2)
```

## tests/privacy/test_log_confidentiality.py

- SHA-256：`aeb67e480a102f9ff53269c01c218a4f9656e27bc7e6fb0810916a63cc6d3d2f`
- 字节数：9472

```
"""Privacy regression: logs and reports carry no body text or
sensitive headers (P032 T011, scenarios 9–10).

Acceptance scenarios (IMPLEMENTATION_PLAN T011, PROJECT_BOOK §7.12
I-12, §17.2):

9.  logs do not contain body text;
10. logs do not contain sensitive request headers.

Verified at three levels: the privacy scanners themselves
(positive/negative on crafted text), the live run (a real healthy
four-experiment run over loopback — its step log, failures, origin
event log and serialised observations are audited, and the logging
system is captured to prove nothing is emitted), and the frozen
evidence on disk (all 48 JSON reports in evidence/Reports/).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import dataclasses
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts")
)

from s0_harness import run_scenario  # noqa: E402
from accepttwin.privacy import (
    FORBIDDEN_REPORT_KEYS,
    SENTINELS,
    PrivacyError,
    assert_log_clean,
    assert_report_clean,
    find_forbidden_keys,
    scan_text_for_body,
    scan_text_for_sensitive_headers,
    scan_text_for_sentinels,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"
REPORTS_DIR = ROOT / "evidence" / "Reports"

MARKER_BODY = (
    "<html><body>UNIQUE-MARKER-BODY-9f3c21 "
    "AT_HTML_SENTINEL_001</body></html>"
)


# ---------------------------------------------------------------------------
# The scanners themselves — positive and negative
# ---------------------------------------------------------------------------


def test_scan_sensitive_headers_finds_all_four_names():
    text = (
        "request failed\n"
        "Authorization: Bearer SECRET-TOKEN\n"
        "Cookie: session=SECRET-VALUE\n"
        "proxy-authorization: Basic dXNlcjpwYXNz\n"
        "Set-Cookie: id=SECRET; Path=/\n"
    )
    assert scan_text_for_sensitive_headers(text) == [
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
    ]


@pytest.mark.parametrize("name", ["AUTHORIZATION", "Cookie", "PROXY-AUTHORIZATION"])
def test_scan_sensitive_headers_is_case_insensitive(name):
    assert scan_text_for_sensitive_headers(f"{name}: secret") == [
        name.lower()
    ]


def test_scan_sensitive_headers_finds_json_keys():
    text = '{"headers": {"authorization": "Bearer SECRET", "cookie": "s=1"}}'
    assert scan_text_for_sensitive_headers(text) == [
        "authorization",
        "cookie",
    ]


def test_scan_sensitive_headers_clean_text_passes():
    text = (
        "Accept: text/html\n"
        "Accept-Encoding: identity\n"
        "User-Agent: AcceptTwin/1.0.0\n"
        "Accept-Language: en\n"
        "status=200 content_type=text/html; charset=utf-8\n"
        "body_sha256=ab12... sentinel_match=true\n"
    )
    assert scan_text_for_sensitive_headers(text) == []


def test_scan_sentinels_finds_both_literals():
    text = "body contained AT_HTML_SENTINEL_001 and AT_MARKDOWN_SENTINEL_001"
    assert scan_text_for_sentinels(text) == list(SENTINELS)


def test_scan_sentinels_clean_text_passes():
    assert scan_text_for_sentinels("sentinel_match=true body_sha256=ab12") == []


def test_scan_body_finds_verbatim_body():
    assert scan_text_for_body(f"log line {MARKER_BODY} end", MARKER_BODY) is True
    assert scan_text_for_body("unrelated log line", MARKER_BODY) is False
    assert scan_text_for_body("log", b"short") is False  # < 8 chars: ignored
    assert scan_text_for_body("log", "") is False


def test_assert_log_clean_accepts_hashes_and_flags():
    assert_log_clean(
        "step 05 ok body_sha256=ab12cd34 sentinel_match=true status=200",
        bodies=(MARKER_BODY,),
    )


def test_assert_log_clean_rejects_body_text():
    with pytest.raises(PrivacyError, match="raw response body text"):
        assert_log_clean(f"saw body: {MARKER_BODY}", bodies=(MARKER_BODY,))


def test_assert_log_clean_rejects_sensitive_header():
    with pytest.raises(PrivacyError, match="sensitive request header"):
        assert_log_clean("Authorization: Bearer SECRET-TOKEN")


def test_assert_log_clean_rejects_sentinel_literal():
    with pytest.raises(PrivacyError, match="Sentinel literal"):
        assert_log_clean("body contained AT_HTML_SENTINEL_001")


def test_assert_log_clean_never_echoes_the_secret():
    try:
        assert_log_clean("Authorization: Bearer DO-NOT-ECHO-ME-12345")
    except PrivacyError as exc:
        assert "DO-NOT-ECHO-ME-12345" not in str(exc)
    else:  # pragma: no cover - the audit must raise here
        raise AssertionError("assert_log_clean did not raise")


# ---------------------------------------------------------------------------
# Cross-check: the frozen forbidden-key set is the same everywhere
# ---------------------------------------------------------------------------


def test_forbidden_key_set_matches_report_builder_and_embed_script():
    """The ban must not silently narrow in any one layer (T009/T010)."""
    from accepttwin.report_builder import _FORBIDDEN_KEYS as builder_keys

    embed_text = (ROOT / "scripts" / "embed_report.py").read_text(
        encoding="utf-8"
    )
    assert FORBIDDEN_REPORT_KEYS == builder_keys
    for key in FORBIDDEN_REPORT_KEYS:
        assert f'"{key}"' in embed_text


def test_sentinel_literals_match_the_frozen_contract():
    """The scanner's literals are the contract's Sentinels (§5.1.2)."""
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_sentinels = {
        rep["sentinel"] for rep in data["representations"].values()
    }
    assert set(SENTINELS) == contract_sentinels
    assert len(SENTINELS) == 2


# ---------------------------------------------------------------------------
# Scenario 9 — live: a real run's logs contain no body text
# ---------------------------------------------------------------------------


def _run_c01():
    """A real healthy four-experiment run (frozen C01 Golden)."""
    return run_scenario("C01", namespace_prefix="t011-C01-logs")


def test_live_run_logs_contain_no_body_text(caplog):
    """The runner's own records and the logging system stay body-free."""
    with caplog.at_level(logging.DEBUG):
        outcome = _run_c01()
    assert outcome.production.verdict == "PASS_OBSERVED"
    # (a) nothing was emitted to the logging system at all: the HTTP
    # handlers suppress log_message and no module logs bodies (§7.12).
    assert caplog.records == []
    # (b) the run's own records carry hashes/flags, never body text.
    blob = json.dumps(
        {
            "evidence": outcome.run.as_dict(),
            "events": [
                dataclasses.asdict(event)
                for event in outcome.adj_origin_events
            ],
        },
        ensure_ascii=False,
        default=str,
    )
    assert "AT_HTML_SENTINEL_001" not in blob
    assert "AT_MARKDOWN_SENTINEL_001" not in blob
    assert_log_clean(blob, bodies=(MARKER_BODY,))
    assert find_forbidden_keys(json.loads(blob)) == []


def test_live_run_origin_events_carry_no_headers_or_body():
    """Origin events record method/path/accept/status only (§5.3)."""
    outcome = _run_c01()
    events = outcome.adj_origin_events
    assert 6 <= len(events) <= 8
    for event in events:
        fields = set(dataclasses.asdict(event))
        assert fields.isdisjoint({"authorization", "cookie", "headers", "body"})
        assert event.accept in ("text/html", "text/markdown")


# ---------------------------------------------------------------------------
# Scenario 10 — live + frozen evidence: no sensitive headers anywhere
# ---------------------------------------------------------------------------


def test_live_run_records_contain_no_sensitive_headers():
    outcome = _run_c01()
    blob = json.dumps(
        {
            "evidence": outcome.run.as_dict(),
            "events": [
                dataclasses.asdict(event)
                for event in outcome.adj_origin_events
            ],
        },
        ensure_ascii=False,
        default=str,
    )
    assert scan_text_for_sensitive_headers(blob) == []
    assert find_forbidden_keys(json.loads(blob)) == []


def test_all_48_frozen_reports_are_clean():
    """All 48 saved JSON reports: no forbidden keys, no Sentinels."""
    import re

    reports = [
        path
        for path in sorted(REPORTS_DIR.glob("*.json"))
        if re.fullmatch(r"[CE]\d\d", path.stem)
    ]
    assert len(reports) == 48
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        assert_report_clean(report)  # raises on any violation
        assert scan_text_for_sensitive_headers(
            path.read_text(encoding="utf-8")
        ) == []
    # The summary file (the 49th JSON) must be clean as well.
    assert_report_clean(
        json.loads((REPORTS_DIR / "REPORTS_SUMMARY.json").read_text(
            encoding="utf-8"
        ))
    )


def test_report_audit_rejects_tainted_dict_at_any_depth():
    """Positive control for the report audit: a tainted dict fails."""
    assert_report_clean({"verdict": "PASS_OBSERVED", "body_sha256": "ab12"})
    with pytest.raises(PrivacyError, match="forbidden key"):
        assert_report_clean({"observations": [{"BODY": "secret"}]})
    with pytest.raises(PrivacyError, match="Sentinel literal"):
        assert_report_clean({"reasons": ["saw AT_HTML_SENTINEL_001"]})
```

## tests/privacy/test_loopback_guard.py

- SHA-256：`1bc62b1e61ef930bf6400947264fb693c43cf372c7dd0e671e305c63f3ba0e86`
- 字节数：6915

```
"""Privacy regression: loopback URL guard (P032 T011, scenarios 1–3).

Acceptance scenarios (IMPLEMENTATION_PLAN T011, PROJECT_BOOK §5.1.1,
§17.4 items 1–3):

1. public IPv4 rejected;
2. public IPv6 rejected;
3. DNS resolving to a non-loopback address rejected.

Each scenario has a positive case (loopback accepted) and negative
cases (rejected). The DNS cases are tested by monkeypatching
``socket.getaddrinfo`` — no real DNS lookup and no network access —
because the guard's job is to judge *whatever addresses resolution
returns*, and the fake lets us feed it a public address, a mixed
loopback+public answer, and a loopback-only answer deterministically.
Literal-IP cases need no resolution at all.
"""

from __future__ import annotations

import socket

import pytest

from accepttwin.privacy import PrivacyError, check_loopback_url
from accepttwin.url_guard import validate_loopback_url


# ---------------------------------------------------------------------------
# Scenario 1 — public IPv4 rejected (positive: loopback accepted)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:18765/doc",
        "http://127.0.0.1/doc",
        "http://127.0.0.2:8080/",
        "http://127.255.255.255/",
    ],
)
def test_loopback_ipv4_accepted(url):
    assert check_loopback_url(url).host.startswith("127.")
    # The underlying T002 guard agrees (regression layer delegates).
    assert validate_loopback_url(url).url == url


@pytest.mark.parametrize(
    "url",
    [
        "http://93.184.216.34/doc",  # public IPv4 (example.com)
        "http://8.8.8.8/",
        "http://1.1.1.1:80/",
        "http://192.168.1.1/doc",  # private LAN — still not loopback (§5.1.1)
        "http://10.0.0.1/doc",
        "http://172.16.0.1/doc",
        "http://0.0.0.0/doc",
        "http://128.0.0.1/doc",  # one past the loopback block
        "http://126.255.255.255/doc",
    ],
)
def test_public_or_non_loopback_ipv4_rejected(url):
    with pytest.raises(PrivacyError):
        check_loopback_url(url)


# ---------------------------------------------------------------------------
# Scenario 2 — public IPv6 rejected (positive: ::1 accepted)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://[::1]:18766/doc",
        "http://[::1]/doc",
    ],
)
def test_loopback_ipv6_accepted(url):
    validated = check_loopback_url(url)
    assert validated.host == "::1"


@pytest.mark.parametrize(
    "url",
    [
        "http://[2606:4700:4700::1111]/",  # public IPv6
        "http://[2001:4860:4860::8888]/",
        "http://[fe80::1]/",  # link-local — not loopback
        "http://[::]/",  # unspecified — not loopback
        "http://[::ffff:93.184.216.34]/",  # IPv4-mapped public address
    ],
)
def test_public_or_non_loopback_ipv6_rejected(url):
    with pytest.raises(PrivacyError):
        check_loopback_url(url)


# ---------------------------------------------------------------------------
# Scenario 3 — DNS resolving to a non-loopback address rejected
# ---------------------------------------------------------------------------


def _fake_getaddrinfo_factory(answers):
    """Return a getaddrinfo replacement serving *answers* for any host.

    *answers* maps host -> list of address strings. Unknown hosts fall
    through to the real resolver (only used for hosts we never query).
    """
    real = socket.getaddrinfo

    def fake(host, port, family=0, type=0, proto=0, flags=0):
        if host in answers:
            infos = []
            for addr in answers[host]:
                if ":" in addr:
                    infos.append(
                        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (addr, port, 0, 0))
                    )
                else:
                    infos.append(
                        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, port))
                    )
            return infos
        return real(host, port, family, type, proto, flags)

    return fake


def test_dns_resolving_to_public_ipv4_rejected(monkeypatch):
    """A name that resolves to a public address is rejected (§17.4.2)."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory({"host.example": ["93.184.216.34"]}),
    )
    with pytest.raises(PrivacyError, match="non-loopback"):
        check_loopback_url("http://host.example:18765/doc")


def test_dns_resolving_to_public_ipv6_rejected(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory(
            {"host.example": ["2606:4700:4700::1111"]}
        ),
    )
    with pytest.raises(PrivacyError, match="non-loopback"):
        check_loopback_url("http://host.example/doc")


def test_dns_mixed_loopback_and_public_rejected(monkeypatch):
    """One non-loopback answer poisons the whole name (fail-closed)."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory(
            {"host.example": ["127.0.0.1", "93.184.216.34"]}
        ),
    )
    with pytest.raises(PrivacyError, match="non-loopback"):
        check_loopback_url("http://host.example/doc")


def test_dns_resolving_to_loopback_only_accepted(monkeypatch):
    """Positive case: a name resolving only to loopback is accepted."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory({"host.example": ["127.0.0.1", "::1"]}),
    )
    validated = check_loopback_url("http://host.example:18765/doc")
    assert set(validated.addresses) == {"127.0.0.1", "::1"}


def test_localhost_resolves_to_loopback_without_mock():
    """Real resolution of localhost must be loopback-only (§5.1.1)."""
    validated = check_loopback_url("http://localhost:18765/doc")
    assert validated.addresses
    assert all(
        addr.startswith("127.") or addr == "::1"
        for addr in validated.addresses
    )


def test_unresolvable_host_rejected(monkeypatch):
    """A name that does not resolve is rejected, never trusted."""
    def boom(host, port, family=0, type=0, proto=0, flags=0):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    with pytest.raises(PrivacyError, match="cannot resolve"):
        check_loopback_url("http://nonexistent.invalid/doc")


# --- guard extras pinned by the same section (scheme / userinfo) --------


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/doc",
        "http://user@127.0.0.1/doc",
        "http://user:pass@127.0.0.1/doc",
        "http://127.0.0.1/doc#frag",
        "ftp://127.0.0.1/doc",
    ],
)
def test_non_http_or_userinfo_or_fragment_rejected(url):
    with pytest.raises(PrivacyError):
        check_loopback_url(url)
```

## tests/privacy/test_privacy_request_headers.py

- SHA-256：`d8057e886699187143dfeb86e255296ae7a8d0c7ac019c34377cc878dcbf0cb2`
- 字节数：6837

```
"""Privacy regression: fixed request-header whitelist (P032 T011).

Acceptance scenarios (IMPLEMENTATION_PLAN T011, PROJECT_BOOK §5.1.3,
§17.2):

5. non-whitelisted request header rejected;
6. Authorization rejected;
7. Cookie rejected.

Each scenario has a positive case (the exact fixed set is accepted)
and negative cases (rejected, in several casings). Rejection is
verified at three levels: the whitelist validator, the privacy
re-raise, and the contract loader — a contract that smuggles a
sensitive header is refused at load time, before any request is
sent, so no I/O can ever carry it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from accepttwin.contract import parse_contract
from accepttwin.privacy import PrivacyError, check_request_headers
from accepttwin.request_headers import (
    build_request_headers,
    validate_request_headers,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"


def fixed_headers(representation="html"):
    return build_request_headers(representation)


# ---------------------------------------------------------------------------
# Positive cases — the exact fixed set is accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("representation", ["html", "markdown"])
def test_fixed_header_set_accepted(representation):
    headers = fixed_headers(representation)
    assert validate_request_headers(headers) == []
    assert check_request_headers(headers) == headers
    assert headers["Accept"] in ("text/html", "text/markdown")


def test_fixed_header_set_accepted_with_different_casing():
    """Header names are case-insensitive (RFC 9110 §5.1); values exact."""
    headers = {
        "accept": "text/html",
        "ACCEPT-ENCODING": "identity",
        "user-agent": "AcceptTwin/1.0.0",
        "Accept-Language": "en",
    }
    assert validate_request_headers(headers) == []
    assert check_request_headers(headers)["Accept"] == "text/html"


# ---------------------------------------------------------------------------
# Scenario 5 — non-whitelisted request header rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "Referer",
        "Origin",
        "Cache-Control",
        "X-Custom",
        "X-AcceptTwin-Debug",
        "x-trace-id",
        "DNT",
        "Accept-Charset",
    ],
)
def test_non_whitelisted_header_rejected(name):
    headers = {**fixed_headers(), name: "something"}
    assert validate_request_headers(headers)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


@pytest.mark.parametrize(
    "headers",
    [
        {"Accept": "text/html"},  # missing the three fixed common headers
        {
            "Accept": "text/html",
            "Accept-Encoding": "gzip",  # wrong fixed value
            "User-Agent": "AcceptTwin/1.0.0",
            "Accept-Language": "en",
        },
        {
            "Accept": "application/json",  # wrong Accept value
            "Accept-Encoding": "identity",
            "User-Agent": "AcceptTwin/1.0.0",
            "Accept-Language": "en",
        },
        {
            "Accept": "text/html",
            "Accept-Encoding": "identity",
            "User-Agent": "AcceptTwin/2.0.0",  # wrong User-Agent
            "Accept-Language": "en",
        },
    ],
)
def test_altered_or_incomplete_fixed_set_rejected(headers):
    assert validate_request_headers(headers)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


def test_duplicate_header_differing_only_by_case_rejected():
    """Two names differing only by case are a duplicate (§5.1.3)."""
    from accepttwin.request_headers import validate_request_headers as v

    class DupMapping(dict):
        def items(self):  # noqa: D102 - test double
            return [
                ("Accept", "text/html"),
                ("accept", "text/markdown"),
                ("Accept-Encoding", "identity"),
                ("User-Agent", "AcceptTwin/1.0.0"),
                ("Accept-Language", "en"),
            ]

    assert v(DupMapping())


# ---------------------------------------------------------------------------
# Scenario 6 — Authorization rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["Authorization", "AUTHORIZATION", "authorization", "AuThorization"],
)
def test_authorization_rejected_in_any_casing(name):
    headers = {**fixed_headers(), name: "Bearer SECRET-TOKEN"}
    errors = validate_request_headers(headers)
    assert any("authorization" in err for err in errors)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


def test_proxy_authorization_rejected():
    headers = {**fixed_headers(), "Proxy-Authorization": "Basic dXNlcjpwYXNz"}
    assert validate_request_headers(headers)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


# ---------------------------------------------------------------------------
# Scenario 7 — Cookie rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["Cookie", "COOKIE", "cookie", "CoOkIe"]
)
def test_cookie_rejected_in_any_casing(name):
    headers = {**fixed_headers(), name: "session=SECRET-VALUE"}
    errors = validate_request_headers(headers)
    assert any("cookie" in err for err in errors)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


# ---------------------------------------------------------------------------
# System level — a contract carrying a sensitive header is refused
# at load time, before any request can be sent
# ---------------------------------------------------------------------------


def _contract_with_header(name, value):
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    # Contract-level fixed headers live under request_headers; inject
    # the forbidden header there so the loader must reject it.
    data["request_headers"][name] = value
    return data


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("Authorization", "Bearer SECRET-TOKEN"),
        ("Cookie", "session=SECRET-VALUE"),
        ("Proxy-Authorization", "Basic dXNlcjpwYXNz"),
        ("X-Custom", "1"),
    ],
)
def test_contract_with_sensitive_header_refused_at_load(name, value):
    with pytest.raises(ValueError, match="request_headers"):
        parse_contract(_contract_with_header(name, value))


def test_clean_contract_loads():
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert parse_contract(data) is not None
```

## tests/privacy/test_redirect_and_proxy.py

- SHA-256：`ad15d448379fcf44548c5f38fe43d2e011c06c35cda00c904ef070c6ca3539c8`
- 字节数：7042

```
"""Privacy regression: redirects and environment proxies (P032 T011).

Acceptance scenario 4 — redirects are not followed (§0.2 item 6,
§17.4 item 4) — plus the §17.4 item 5 boundary the T005 runner
already implements (environment proxies are never read): both are
verified here against real loopback HTTP servers, with the
environment deliberately poisoned with a dead proxy.

No test contacts a public address: the redirect *target* is a second
loopback server whose hit counter proves it was never contacted, and
the public-URL redirect case asserts the client returns the 301
itself after exactly one request to the local server.
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from accepttwin.experiment_runner import _http_get


class _CountingHandler(BaseHTTPRequestHandler):
    """Serves one fixed response; counts every request received."""

    protocol_version = "HTTP/1.1"
    response_status = 200
    response_body = b"ok"
    location = None  # when set: send this Location with a 301
    hits = 0

    def log_message(self, *args):  # silence stderr logging
        return

    def do_GET(self):
        type(self).hits += 1
        body = type(self).response_body
        if type(self).location is not None:
            self.send_response(301)
            self.send_header("Location", type(self).location)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve(handler_cls):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@pytest.fixture
def reset_handler():
    _CountingHandler.hits = 0
    _CountingHandler.location = None
    _CountingHandler.response_status = 200
    _CountingHandler.response_body = b"ok"
    yield _CountingHandler
    _CountingHandler.hits = 0
    _CountingHandler.location = None


# ---------------------------------------------------------------------------
# Scenario 4 — redirects are not followed
# ---------------------------------------------------------------------------


def test_redirect_to_loopback_target_is_not_followed(reset_handler):
    """A 301 to another loopback URL is returned as-is; target: 0 hits."""
    target = _serve(reset_handler)
    try:
        target_port = target.server_address[1]
        redirector_cls = type(
            "Redirector",
            (_CountingHandler,),
            {"location": f"http://127.0.0.1:{target_port}/target", "hits": 0},
        )
        redirector = _serve(redirector_cls)
        try:
            redirector_port = redirector.server_address[1]
            result = _http_get(
                f"http://127.0.0.1:{redirector_port}/old",
                "html",
                timeout=5.0,
            )
            status, headers, body = result.status, result.headers, result.body
            assert status == 301
            assert headers.get("location") == (
                f"http://127.0.0.1:{target_port}/target"
            )
            assert body == b""
        finally:
            redirector.shutdown()
            redirector.server_close()
    finally:
        target.shutdown()
        target.server_close()
    # The redirector was hit exactly once; the target was never hit —
    # the 301 was observed, not followed.
    assert redirector_cls.hits == 1
    assert _CountingHandler.hits == 0


def test_redirect_to_public_url_is_not_followed(reset_handler):
    """A 301 to a public URL is returned as-is; nothing is fetched."""
    redirector_cls = type(
        "Redirector",
        (_CountingHandler,),
        {"location": "http://93.184.216.34/elsewhere", "hits": 0},
    )
    redirector = _serve(redirector_cls)
    try:
        port = redirector.server_address[1]
        result = _http_get(
            f"http://127.0.0.1:{port}/old", "html", timeout=5.0
        )
        status, headers, body = result.status, result.headers, result.body
        assert status == 301
        assert headers.get("location") == "http://93.184.216.34/elsewhere"
        assert body == b""
        # Exactly one request reached the local server: the client made
        # no second connection anywhere.
        assert redirector_cls.hits == 1
    finally:
        redirector.shutdown()
        redirector.server_close()


def test_direct_200_still_works(reset_handler):
    """Positive case: a plain 200 response is observed normally."""
    server = _serve(reset_handler)
    try:
        port = server.server_address[1]
        result = _http_get(
            f"http://127.0.0.1:{port}/doc", "html", timeout=5.0
        )
        status, headers, body = result.status, result.headers, result.body
        assert status == 200
        assert body == b"ok"
        assert reset_handler.hits == 1
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# §17.4 item 5 — environment proxies are never read
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "var",
    ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"],
)
def test_dead_environment_proxy_is_ignored(reset_handler, monkeypatch, var):
    """With a dead proxy in the environment, local GETs still succeed.

    The client opens a TCP connection to the URL's own host/port and
    never consults proxy variables (T005); if it did, every request
    would fail against the dead 127.0.0.1:1 proxy.
    """
    monkeypatch.setenv(var, "http://127.0.0.1:1")
    server = _serve(reset_handler)
    try:
        port = server.server_address[1]
        result = _http_get(
            f"http://127.0.0.1:{port}/doc", "markdown", timeout=5.0
        )
        status, body = result.status, result.body
        assert status == 200
        assert body == b"ok"
    finally:
        server.shutdown()
        server.server_close()


def test_all_environment_proxies_poisoned_at_once(reset_handler, monkeypatch):
    """Positive control for the parametrised case: all vars poisoned."""
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "NO_PROXY"):
        monkeypatch.setenv(var, "http://127.0.0.1:1")
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:1"
    server = _serve(reset_handler)
    try:
        port = server.server_address[1]
        result = _http_get(
            f"http://127.0.0.1:{port}/doc", "html", timeout=5.0
        )
        status, body = result.status, result.body
        assert (status, body) == (200, b"ok")
    finally:
        server.shutdown()
        server.server_close()
```

## tests/unit/independent_schema_validator.py

- SHA-256：`5c3878c8651421cddd3b99f3bf43304360d0e25c57d9928081445f19730b4b23`
- 字节数：8964

```
"""Independent minimal JSON Schema validator (P032 T009).

This module is the *independent* check on ``accepttwin.report/v1``:
it reads only the Schema file
(``schemas/accepttwin.report.v1.schema.json``) and validates plain
JSON data against it, using only the Python standard library. It
deliberately does **not** import ``accepttwin.report_builder`` (or
any other production module): a report that passes here passed a
checker that shares no code with the generator, so the generator
cannot validate itself into a PASS.

Supported keywords (the subset the report Schema uses): ``$ref``
(local ``#/$defs/...`` only), ``$defs``, ``type`` (string or list),
``const``, ``enum``, ``required``, ``properties``,
``additionalProperties`` (boolean or schema), ``pattern`` (ECMA-style
regular expression, applied with search semantics as JSON Schema
specifies), ``minimum``, ``maximum``, ``minLength``, ``items``, ``minItems``,
``maxItems``, ``propertyNames``. Anything else in the Schema is
ignored by this validator — if the Schema ever gains a keyword
this module does not understand, validation silently weakens, so
``test_report_schema.py`` asserts the Schema uses only these
keywords.

Limitations, stated plainly: this is a *minimal* validator, not a
full JSON Schema implementation. It does not implement ``format``,
``allOf``/``anyOf``/``oneOf``/``not`` (other than inside
``propertyNames`` via ``pattern``), ``$dynamicRef``, remote ``$ref``,
or numeric ``multipleOf``/``exclusiveMinimum``. The report Schema
is written to stay inside the supported subset.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

__all__ = ["SchemaError", "load_schema", "validate", "validate_report_file"]

#: Keywords this validator understands. Anything else in the Schema
#: is ignored — see the module docstring.
SUPPORTED_KEYWORDS: frozenset[str] = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "const",
        "enum",
        "items",
        "maxItems",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "pattern",
        "properties",
        "propertyNames",
        "required",
        "type",
    }
)

_DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "accepttwin.report.v1.schema.json"
)


class SchemaError(ValueError):
    """Raised when the Schema file itself cannot be loaded."""


def load_schema(path: str | Path | None = None) -> dict[str, Any]:
    """Read and return the report Schema as plain JSON data."""
    schema_path = Path(path) if path is not None else _DEFAULT_SCHEMA_PATH
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SchemaError(
            f"cannot load report schema {schema_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SchemaError(f"report schema {schema_path} must be a JSON object")
    return data


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, (int, float)) and not isinstance(value, bool))
    if expected == "null":
        return value is None
    return False


def _resolve(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a local ``#/...`` reference against the Schema root."""
    if not ref.startswith("#/"):
        raise SchemaError(f"only local refs are supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise SchemaError(f"unresolvable ref {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise SchemaError(f"ref {ref!r} does not point at a schema object")
    return node


def _validate(
    instance: Any, schema: dict[str, Any], root: dict[str, Any], path: str
) -> list[str]:
    """Return the list of validation errors for *instance* at *path*."""
    errors: list[str] = []
    if "$ref" in schema:
        errors.extend(_validate(instance, _resolve(schema["$ref"], root), root, path))
        return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must be {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']!r}, got {instance!r}")
    expected_type = schema.get("type")
    if expected_type is not None:
        types = [expected_type] if isinstance(expected_type, str) else expected_type
        if not any(_type_matches(instance, t) for t in types):
            errors.append(
                f"{path}: must be of type {types!r}, got {type(instance).__name__} ({instance!r})"
            )
            return errors  # further keyword checks assume the type
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(
                f"{path}: string is too short (minimum {schema['minLength']})"
            )
        if "pattern" in schema:
            try:
                if re.search(schema["pattern"], instance) is None:
                    errors.append(
                        f"{path}: {instance!r} does not match pattern {schema['pattern']!r}"
                    )
            except re.error as exc:
                errors.append(f"{path}: invalid pattern {schema['pattern']!r}: {exc}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance!r} is less than minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance!r} is greater than maximum {schema['maximum']}")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors.extend(
                    _validate(value, properties[key], root, child_path)
                )
            elif "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                if extra is False:
                    errors.append(f"{path}: additional property {key!r} is not allowed")
                elif isinstance(extra, dict):
                    errors.extend(_validate(value, extra, root, child_path))
        if "propertyNames" in schema:
            name_schema = schema["propertyNames"]
            for key in instance:
                name_errors = _validate(key, name_schema, root, f"{path} (property name)")
                errors.extend(name_errors)
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(
                f"{path}: array has {len(instance)} items, minimum {schema['minItems']}"
            )
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(
                f"{path}: array has {len(instance)} items, maximum {schema['maxItems']}"
            )
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(
                    _validate(item, schema["items"], root, f"{path}[{index}]")
                )
    return errors


def validate(
    instance: Any, schema: dict[str, Any] | None = None
) -> list[str]:
    """Validate *instance* against the report Schema.

    Returns the list of error strings (empty means valid). *schema*
    defaults to the Schema file on disk; pass an explicit parsed
    schema only in validator self-tests.
    """
    root = schema if schema is not None else load_schema()
    if not isinstance(root, dict):
        raise SchemaError("schema must be a JSON object")
    return _validate(instance, root, root, "$")


def validate_report_file(path: str | Path) -> list[str]:
    """Validate the JSON report file at *path*; return error strings."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path}: cannot read report JSON: {exc}"]
    return validate(data)
```

## tests/unit/test_cache_evidence.py

- SHA-256：`04d60decaddd0b7c7e605730cc0cfd74eee33d476b9d42b57af97c1df4ae5bc9`
- 字节数：9792

```
"""Unit tests for the dual-evidence cache-state verifier (P032 T004).

The verifier is pure logic (no I/O, no HTTP): every case below feeds
crafted header + behaviour evidence to
:func:`accepttwin.cache_evidence.verify_cache_state` and checks the
confirmed state, or ``CACHE_STATE_UNKNOWN`` when any leg is missing
or the legs conflict (PROJECT_BOOK §5.3 D).

End-to-end dual evidence — real HTTP through the proxy, real origin
counter deltas, real snapshots — is exercised in
``tests/integration/test_cache_proxy.py``.
"""

from __future__ import annotations

import pytest

from accepttwin.cache_evidence import (
    CACHE_STATE_UNKNOWN,
    BehaviorEvidence,
    CacheEvidenceResult,
    HeaderEvidence,
    verify_cache_state,
)

KEY = "a" * 64
ENTRY = "entry-" + "b" * 16


def header(status, key=KEY, entry=ENTRY):
    return HeaderEvidence(status=status, cache_key_sha256=key, entry_id=entry)


def behavior(**overrides):
    base = {
        "origin_counter_delta": 1,
        "origin_event_present": True,
        "entry_created": True,
        "entry_id_matches": True,
        "body_hash_matches": True,
        "entry_count_delta": 0,
    }
    base.update(overrides)
    return BehaviorEvidence(**base)


# ---------------------------------------------------------------------------
# Confirmed states (§5.3 A–C)
# ---------------------------------------------------------------------------


def test_miss_confirmed_when_both_legs_hold():
    result = verify_cache_state(header("MISS"), behavior())
    assert result.state == "MISS"
    assert result.verified is True
    assert bool(result) is True


def test_hit_confirmed_when_both_legs_hold():
    result = verify_cache_state(
        header("HIT"), behavior(origin_counter_delta=0)
    )
    assert result.state == "HIT"
    assert result.verified is True


def test_bypass_confirmed_when_both_legs_hold():
    result = verify_cache_state(header("BYPASS"), behavior())
    assert result.state == "BYPASS"
    assert result.verified is True


def test_bypass_confirmed_without_cache_key():
    # §5.3 C lists only the status header for BYPASS; the key is not a
    # required leg (the proxy emits one anyway, but its absence must
    # not turn a confirmed BYPASS into UNKNOWN).
    result = verify_cache_state(
        header("BYPASS", key=None, entry=None), behavior()
    )
    assert result.state == "BYPASS"
    assert result.verified is True


def test_expected_state_matching_is_accepted():
    assert verify_cache_state(header("MISS"), behavior(), expected="MISS").state == "MISS"
    assert (
        verify_cache_state(
            header("HIT"), behavior(origin_counter_delta=0), expected="HIT"
        ).state
        == "HIT"
    )
    assert (
        verify_cache_state(header("BYPASS"), behavior(), expected="BYPASS").state
        == "BYPASS"
    )


# ---------------------------------------------------------------------------
# Missing header leg (§5.3 D)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["MISS", "HIT", "BYPASS"])
def test_missing_status_header_is_unknown(status):
    result = verify_cache_state(
        HeaderEvidence(status=None), behavior(origin_counter_delta=0)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert result.verified is False
    assert any("missing cache-status" in r for r in result.reasons)


@pytest.mark.parametrize("status", ["MISS", "HIT"])
def test_missing_key_header_is_unknown(status):
    delta = 0 if status == "HIT" else 1
    result = verify_cache_state(
        header(status, key=None), behavior(origin_counter_delta=delta)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("cache-key" in r for r in result.reasons)


@pytest.mark.parametrize("status", ["MISS", "HIT"])
def test_missing_entry_id_header_is_unknown(status):
    delta = 0 if status == "HIT" else 1
    result = verify_cache_state(
        header(status, entry=None), behavior(origin_counter_delta=delta)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("entry-id" in r for r in result.reasons)


def test_unrecognised_status_value_is_unknown():
    result = verify_cache_state(header("STALE"), behavior())
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("unrecognised" in r for r in result.reasons)


def test_empty_status_header_is_unknown():
    result = verify_cache_state(header(""), behavior())
    assert result.state == CACHE_STATE_UNKNOWN


# ---------------------------------------------------------------------------
# Missing behaviour leg (§5.3 D)
# ---------------------------------------------------------------------------


def test_miss_without_measured_counter_delta_is_unknown():
    result = verify_cache_state(
        header("MISS"), behavior(origin_counter_delta=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("counter delta" in r for r in result.reasons)


def test_hit_without_measured_counter_delta_is_unknown():
    result = verify_cache_state(
        header("HIT"), behavior(origin_counter_delta=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_bypass_without_measured_counter_delta_is_unknown():
    result = verify_cache_state(
        header("BYPASS"), behavior(origin_counter_delta=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_miss_without_origin_event_check_is_unknown():
    result = verify_cache_state(
        header("MISS"), behavior(origin_event_present=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("origin event" in r for r in result.reasons)


def test_miss_without_entry_creation_check_is_unknown():
    result = verify_cache_state(header("MISS"), behavior(entry_created=None))
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("entry creation" in r for r in result.reasons)


def test_hit_without_entry_id_check_is_unknown():
    result = verify_cache_state(
        header("HIT"),
        behavior(origin_counter_delta=0, entry_id_matches=None),
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("entry-id match" in r for r in result.reasons)


def test_hit_without_body_hash_check_is_unknown():
    result = verify_cache_state(
        header("HIT"),
        behavior(origin_counter_delta=0, body_hash_matches=None),
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("body-hash" in r for r in result.reasons)


def test_bypass_without_entry_count_check_is_unknown():
    result = verify_cache_state(
        header("BYPASS"), behavior(entry_count_delta=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("entry-count" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Conflicts between the legs (§5.3 D)
# ---------------------------------------------------------------------------


def test_hit_header_with_counter_increase_is_unknown():
    # §5.3 D: header says HIT but the origin counter increased.
    result = verify_cache_state(
        header("HIT"), behavior(origin_counter_delta=1)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("delta 0" in r for r in result.reasons)


def test_miss_header_with_no_counter_increase_is_unknown():
    # §5.3 D: header says MISS but the origin counter did not move.
    result = verify_cache_state(
        header("MISS"), behavior(origin_counter_delta=0)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("delta +1" in r for r in result.reasons)


def test_bypass_header_with_no_counter_increase_is_unknown():
    result = verify_cache_state(
        header("BYPASS"), behavior(origin_counter_delta=0)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_miss_header_without_matching_origin_event_is_unknown():
    result = verify_cache_state(
        header("MISS"), behavior(origin_event_present=False)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_miss_header_without_created_entry_is_unknown():
    result = verify_cache_state(header("MISS"), behavior(entry_created=False))
    assert result.state == CACHE_STATE_UNKNOWN


def test_hit_header_with_entry_id_mismatch_is_unknown():
    result = verify_cache_state(
        header("HIT"),
        behavior(origin_counter_delta=0, entry_id_matches=False),
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("does not match" in r for r in result.reasons)


def test_hit_header_with_body_hash_mismatch_is_unknown():
    result = verify_cache_state(
        header("HIT"),
        behavior(origin_counter_delta=0, body_hash_matches=False),
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_bypass_header_with_entry_count_increase_is_unknown():
    result = verify_cache_state(
        header("BYPASS"), behavior(entry_count_delta=1)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_header_state_disagreeing_with_expected_is_unknown():
    result = verify_cache_state(header("HIT"), behavior(), expected="MISS")
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("does not match" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_unknown_result_carries_reasons_and_header_status():
    result = verify_cache_state(header("MISS"), behavior(origin_counter_delta=0))
    assert isinstance(result, CacheEvidenceResult)
    assert result.header_status == "MISS"
    assert result.reasons
    assert all(isinstance(r, str) and r for r in result.reasons)


def test_confirmed_result_carries_a_reason():
    result = verify_cache_state(header("MISS"), behavior())
    assert result.reasons
```

## tests/unit/test_canonical_json.py

- SHA-256：`f566cae24f3755a257cd1d8807b04c2fee79d432af76d207ee383583e267bdae`
- 字节数：9804

```
"""Unit tests for Canonical JSON (§10.4) and contract-hash determinism.

Covers: volatile fields (generated time, duration_ms / bare ``duration``,
process id, temporary paths, dynamic ports, ``uuid``, ``request_id``,
receivedAt) never enter the canonical form; keys are sorted; no extra
whitespace; header names lower-cased; repeated hashing of the same contract
is identical (I-08). ``cache_entry_id`` is NOT volatile (§5.3/§8 evidence
field) and is retained.
"""

from __future__ import annotations

import json

from accepttwin.contract import (
    canonical_contract_hash,
    canonical_json_bytes,
    load_contract,
    parse_contract,
)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "contracts" / "site.json"


def test_no_extra_whitespace_and_sorted_keys():
    data = {"b": 1, "a": {"d": 4, "c": 3}}
    assert canonical_json_bytes(data) == b'{"a":{"c":3,"d":4},"b":1}'


def test_volatile_fields_stripped_at_any_depth():
    data = {
        "generated_at": "2026-11-24T13:00:00Z",
        "duration_ms": 12,
        "process_id": 1234,
        "temporary_path": "/tmp/xyz",
        "ephemeral_port": 54321,
        "receivedAt": "2026-11-24T13:00:00Z",
        "received_at": "2026-11-24T13:00:00Z",
        "nested": {
            "generated_at": "2026-11-24T13:00:00Z",
            "duration_ms": 5,
            "keep": "yes",
        },
        "keep": "yes",
    }
    decoded = json.loads(canonical_json_bytes(data))
    assert decoded == {"nested": {"keep": "yes"}, "keep": "yes"}


def test_volatile_uuid_request_id_duration_stripped():
    # P1-01 (§10.4): random UUIDs and non-deterministic cache request IDs
    # (bare ``uuid`` / ``request_id`` / ``duration`` keys) must never enter
    # the canonical form, at any depth.
    data = {
        "uuid": "11111111-2222-3333-4444-555555555555",
        "request_id": "req-9f8e7d6c-1234",
        "duration": 0.042,
        "nested": {
            "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "request_id": "req-other",
            "duration": 1.5,
            "keep": "yes",
        },
        "a": 1,
    }
    decoded = json.loads(canonical_json_bytes(data))
    assert decoded == {"nested": {"keep": "yes"}, "a": 1}
    assert "uuid" not in decoded and "uuid" not in decoded["nested"]
    assert "request_id" not in decoded
    assert "request_id" not in decoded["nested"]
    assert "duration" not in decoded and "duration" not in decoded["nested"]
    # Varying only a volatile value must not change the canonical bytes...
    changed_uuid = dict(data, uuid="99999999-8888-7777-6666-555555555555")
    assert canonical_json_bytes(changed_uuid) == canonical_json_bytes(data)
    # ...while changing a real field must (control: hash still sensitive
    # to genuine input changes).
    changed_real = dict(data, a=2)
    assert canonical_json_bytes(changed_real) != canonical_json_bytes(data)
    # cache_entry_id is an evidence field (§5.3/§8), NOT volatile: retained.
    assert json.loads(
        canonical_json_bytes({"cache_entry_id": "ce-001", "a": 1})
    ) == {"cache_entry_id": "ce-001", "a": 1}


def test_header_names_lowercased_and_values_normalised():
    data = {
        "request_headers": {
            "Accept-Encoding": "  identity  ",
            "User-Agent": "AcceptTwin/1.0.0",
        }
    }
    decoded = json.loads(canonical_json_bytes(data))
    assert decoded == {
        "request_headers": {
            "accept-encoding": "identity",
            "user-agent": "AcceptTwin/1.0.0",
        }
    }


def test_utf8_not_escaped():
    assert "中文".encode("utf-8") in canonical_json_bytes({"name": "中文"})


def test_canonical_bytes_deterministic_across_key_order():
    first = {"a": 1, "b": {"x": 1, "y": 2}, "c": [3, 2, 1]}
    second = {"c": [3, 2, 1], "b": {"y": 2, "x": 1}, "a": 1}
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_contract_hash_ignores_volatile_fields():
    contract = load_contract(EXAMPLE)
    base = canonical_contract_hash(contract)
    # The same contract dict plus volatile noise must hash identically,
    # because volatile fields never enter the canonical form.
    noisy = contract.as_dict()
    noisy.update(
        {
            "generated_at": "2026-11-24T13:00:00Z",
            "duration_ms": 99,
            "process_id": 1,
            "temporary_path": "/tmp/abc",
            "ephemeral_port": 40000,
        }
    )
    assert canonical_json_bytes(noisy) == canonical_json_bytes(
        contract.as_dict()
    )
    assert base == canonical_contract_hash(contract)


def test_hash_repeat_100_consistent():
    contract = load_contract(EXAMPLE)
    expected = canonical_contract_hash(contract)
    assert all(
        canonical_contract_hash(load_contract(EXAMPLE)) == expected
        for _ in range(100)
    )


def test_hash_differs_for_different_contracts():
    one = load_contract(EXAMPLE)
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["contract_id"] = "site-example-002"
    two = parse_contract(data)
    assert canonical_contract_hash(one) != canonical_contract_hash(two)


def test_contract_hash_ignores_loopback_port_change():
    # ADR-003 (T007 P1-1): the same logical contract on two different
    # pairs of OS-assigned loopback ports must hash identically --
    # §10.4 "不包含动态端口". Validation still runs on the real ports:
    # both contracts are valid (same path, different ports each).
    one = load_contract(EXAMPLE)
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["url"] = "http://127.0.0.1:51111/doc"
    data["origin_url"] = "http://127.0.0.1:52222/doc"
    two = parse_contract(data)
    assert canonical_contract_hash(one) == canonical_contract_hash(two)
    # The canonical bytes themselves are equal, and the port slot
    # reads 0 (the ADR-003 placeholder), not the real port.
    decoded = json.loads(canonical_json_bytes(two.as_dict()))
    assert decoded["url"] == "http://127.0.0.1:0/doc"
    assert decoded["origin_url"] == "http://127.0.0.1:0/doc"


def test_contract_hash_port_swap_collides_by_design_t013_f01():
    # T014 / T013-F01 (P2, accepted in ADR-007 — NOT fixed by code).
    # Two contracts differing ONLY by swapping the url/origin_url
    # ports hash identically, by force of §10.4: the hash must be
    # invariant to OS-assigned loopback port values (repeat-100 with
    # fresh pairs must give one hash, §7.8 I-08), and the port values
    # are the only difference between the two contracts. Any hash
    # satisfying §10.4 therefore collides them.
    #
    # The review's first suggested fix (role-distinct placeholders,
    # url -> :0, origin_url -> :1) was implemented and probed in
    # T014: it does NOT distinguish the swap, because the placeholder
    # is a per-key constant — the swapped contract normalises to the
    # very same bytes (url :0, origin_url :1). An order-based
    # placeholder (smaller port -> :0) would distinguish the swap
    # but would make the hash depend on OS allocation order and
    # break repeat-100 determinism, so it is rejected on spec
    # grounds. The residual risk is accepted: execution and
    # validation still use the real ports (the runner connects proxy
    # vs origin by role, never by hash), no Golden scenario
    # distinguishes the pair, and no verdict is affected.
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    url, origin_url = data["url"], data["origin_url"]
    assert url != origin_url
    one = parse_contract(data)
    data["url"], data["origin_url"] = origin_url, url
    two = parse_contract(data)
    assert canonical_contract_hash(one) == canonical_contract_hash(two)
    assert canonical_json_bytes(one.as_dict()) == canonical_json_bytes(
        two.as_dict()
    )


def test_contract_hash_still_sensitive_to_semantic_url_change():
    # ADR-003: normalisation must not over-erase. Changing the path
    # or the host must still change the hash, even when the ports
    # also change.
    one = load_contract(EXAMPLE)
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["url"] = "http://127.0.0.1:51111/other"
    data["origin_url"] = "http://127.0.0.1:52222/other"
    assert canonical_contract_hash(parse_contract(data)) != (
        canonical_contract_hash(one)
    )
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["url"] = "http://localhost:51111/doc"
    data["origin_url"] = "http://localhost:52222/doc"
    assert canonical_contract_hash(parse_contract(data)) != (
        canonical_contract_hash(one)
    )


def test_canonical_json_keeps_non_loopback_port():
    # ADR-003 bounds the normalisation to loopback URLs: a
    # non-loopback host's port is part of the service identity.
    assert canonical_json_bytes(
        {"url": "http://93.184.216.34:8080/doc"}
    ) != canonical_json_bytes({"url": "http://93.184.216.34:9090/doc"})
    # The scheme is preserved, not normalised away (only http loopback
    # ports are rewritten; an https URL keeps its port as-is).
    assert json.loads(
        canonical_json_bytes({"url": "https://127.0.0.1:51111/doc"})
    ) == {"url": "https://127.0.0.1:51111/doc"}
    # A loopback URL without an explicit port is left untouched -- it
    # stays distinct from the explicit-port form.
    assert json.loads(canonical_json_bytes({"url": "http://127.0.0.1/doc"})) == {
        "url": "http://127.0.0.1/doc"
    }
    # IPv6 loopback is normalised the same way.
    assert json.loads(
        canonical_json_bytes({"url": "http://[::1]:51111/doc"})
    ) == {"url": "http://[::1]:0/doc"}
    # An unparseable value is returned unchanged, never raised on.
    assert json.loads(canonical_json_bytes({"url": "not a url"})) == {
        "url": "not a url"
    }
```

## tests/unit/test_classifier.py

- SHA-256：`3499805e3849270c09706ed640bf3de347762b3129dc29cc7ee230e542393b0f`
- 字节数：41043

```
"""Unit tests for the production classifier (P032 T006).

Covers IMPLEMENTATION_PLAN T006 acceptance criteria and PROJECT_BOOK
§6.3 (first-error location), §8 (diagnostics), §9 (five verdicts
and their priority), §7.11 I-11 (Vary never decides a verdict alone)
and §7.12 I-12 (no body text):

* all five verdicts are reachable;
* every diagnostic family is exercised through the classifier;
* origin errors are never misreported as cache bleed;
* a healthy cache without Vary is never misreported as a bleed;
* a HIT/MISS evidence conflict is never misreported as a bleed;
* first-error positions are exact, and a later more severe error
  never rewrites the history;
* a lone 200 / a lone Sentinel match never yields PASS or HIT.

Most cases feed crafted :class:`RequestObservation` objects to
:func:`accepttwin.classifier.classify_run` (pure logic, no I/O).
Two cases at the end run the real T005 runner over loopback and
classify the genuine observations, proving the classifier agrees
with live evidence.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import socket
from pathlib import Path

import pytest

from accepttwin.cache_proxy import ResetEvidence
from accepttwin.classifier import ClassificationResult, classify_run
from accepttwin.contract import Contract, parse_contract
from accepttwin.evidence import RawObservation, RequestObservation
from accepttwin.experiment_runner import run_experiments
from accepttwin.origin_server import OriginEvent

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

HTML_CT = "text/html; charset=utf-8"
MD_CT = "text/markdown; charset=utf-8"
HTML_BODY = "h" * 64
MD_BODY = "m" * 64
KEY = "k" * 64


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_contract(*, mode="variant_by_accept", vary_accept="advisory"):
    """A valid contract; ports are placeholders — the classifier
    never performs I/O, so they only need to pass the loopback guard."""
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if mode == "no_store":
        data["cache_behavior"] = {
            "mode": "no_store",
            "vary_accept": "not_required",
            "max_age_seconds": None,
        }
    else:
        data["cache_behavior"] = {
            "mode": "variant_by_accept",
            "vary_accept": vary_accept,
            "max_age_seconds": 60,
        }
    return parse_contract(data)


def obs(
    index,
    rep,
    *,
    status=200,
    content_type=None,
    sentinel=True,
    cache=None,
    key=KEY,
    entry=None,
    before=0,
    after=0,
    body=None,
):
    """One crafted observation. ``before``/``after`` are cumulative
    origin counters; the delta is derived from them."""
    if content_type is None:
        content_type = HTML_CT if rep == "html" else MD_CT
    if body is None:
        body = HTML_BODY if rep == "html" else MD_BODY
    if entry is None and cache in ("MISS", "HIT"):
        entry = f"entry-{index:03d}"
    experiment = {
        1: "ORIGIN_HTML",
        2: "ORIGIN_MARKDOWN",
        3: "HTML_COLD",
        4: "MARKDOWN_COLD",
        5: "HTML_TO_MARKDOWN",
        6: "HTML_TO_MARKDOWN",
        7: "MARKDOWN_TO_HTML",
        8: "MARKDOWN_TO_HTML",
    }[index]
    return RequestObservation(
        request_index=index,
        experiment_id=experiment,
        requested_representation=rep,
        response_status=status,
        response_content_type=content_type,
        body_sha256=body,
        sentinel_match=sentinel,
        cache_status=cache,
        cache_key_sha256=key if cache in ("MISS", "HIT") else None,
        cache_entry_id=entry,
        origin_counter_before=before,
        origin_counter_after=after,
        origin_counter_delta=after - before,
    )


def healthy_observations(*, cache_mode="variant_by_accept"):
    """The eight observations of a fully healthy run: baselines
    correct, cold requests MISS (or BYPASS under no_store), both
    warm orders MISS (or BYPASS). Counters increase by exactly 1
    per origin visit."""
    state = "BYPASS" if cache_mode == "no_store" else "MISS"
    return [
        obs(1, "html", before=0, after=1),
        obs(2, "markdown", before=1, after=2),
        obs(3, "html", cache=state, before=2, after=3),
        obs(4, "markdown", cache=state, before=3, after=4),
        obs(5, "html", cache=state, before=4, after=5),
        obs(6, "markdown", cache=state, before=5, after=6),
        obs(7, "markdown", cache=state, before=6, after=7),
        obs(8, "html", cache=state, before=7, after=8),
    ]


def resets_ok():
    return [
        ResetEvidence(
            namespace=f"t006-{name}",
            success=True,
            entries_before=1,
            entries_after=0,
            entries_removed=1,
        )
        for name in (
            "html-cold",
            "markdown-cold",
            "html-to-markdown",
            "markdown-to-html",
        )
    ]


def classify(observations, *, contract=None, events=None, resets=None, **kwargs):
    return classify_run(
        contract if contract is not None else build_contract(),
        observations,
        events,
        resets if resets is not None else resets_ok(),
        **kwargs,
    )


def raw(
    index,
    rep,
    *,
    status=200,
    content_type=None,
    sentinel=True,
    cache_header=None,
    body_size=128,
    transport_error=None,
    headers=None,
    event_present=True,
):
    """A RawObservation for the same request, carrying the detail
    RequestObservation cannot: raw cache header, body size,
    transport error, Vary header, origin-event presence."""
    if content_type is None:
        content_type = HTML_CT if rep == "html" else MD_CT
    return RawObservation(
        request_index=index,
        experiment_id="HTML_TO_MARKDOWN" if index in (5, 6) else "HTML_COLD",
        requested_representation=rep,
        method="GET",
        url="http://127.0.0.1:18765/doc",
        accept="text/html" if rep == "html" else "text/markdown",
        response_status=status,
        response_content_type=content_type,
        body_sha256=HTML_BODY if rep == "html" else MD_BODY,
        body_size=body_size,
        sentinel_match=sentinel,
        sentinel_sha256=hashlib.sha256(
            b"AT_HTML_SENTINEL_001" if rep == "html" else b"AT_MARKDOWN_SENTINEL_001"
        ).hexdigest(),
        response_headers=dict(headers) if headers else {},
        cache_status_header=cache_header,
        origin_event_present=event_present,
        transport_error=transport_error,
    )


# ---------------------------------------------------------------------------
# §9.5 PASS_OBSERVED
# ---------------------------------------------------------------------------


def test_healthy_run_passes_with_no_diagnostics():
    result = classify(healthy_observations())
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()
    assert result.first_error is None
    assert result.first_error_experiment_id is None
    assert result.critical_count == 0
    assert result.warning_count == 0


def test_healthy_run_passes_when_observations_unsorted():
    observations = healthy_observations()
    result = classify(list(reversed(observations)))
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None


def test_no_store_bypass_run_passes():
    result = classify(
        healthy_observations(cache_mode="no_store"),
        contract=build_contract(mode="no_store"),
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


def test_result_as_dict_has_no_body_text():
    result = classify(healthy_observations())
    data = result.as_dict()
    assert data["verdict"] == "PASS_OBSERVED"
    assert data["first_error"] is None
    assert "body_text" not in json.dumps(data)


def test_classification_result_rejects_unknown_verdict():
    with pytest.raises(ValueError, match="unknown verdict"):
        ClassificationResult(verdict="MAYBE")


# ---------------------------------------------------------------------------
# §9.1 ORIGIN_NEGOTIATION_ERROR (incl. "never misreported as bleed")
# ---------------------------------------------------------------------------


def test_origin_html_404():
    observations = healthy_observations()
    observations[0] = obs(1, "html", status=404, sentinel=False, before=0, after=1)
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert "ORIGIN_NEGOTIATION_ERROR" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 1
    assert result.first_error_experiment_id == "ORIGIN_HTML"


def test_origin_markdown_404():
    observations = healthy_observations()
    observations[1] = obs(
        2, "markdown", status=404, sentinel=False, before=1, after=2
    )
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert result.first_error == 2
    assert result.first_error_experiment_id == "ORIGIN_MARKDOWN"


def test_origin_markdown_wrong_content_type():
    observations = healthy_observations()
    observations[1] = obs(
        2, "markdown", content_type="text/html", before=1, after=2
    )
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert result.first_error == 2


def test_origin_markdown_sentinel_missing():
    observations = healthy_observations()
    observations[1] = obs(2, "markdown", sentinel=False, before=1, after=2)
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    # The missing Sentinel is kept as secondary evidence (§9.6).
    assert "SENTINEL_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 2


def test_origin_error_beats_later_cache_problem():
    # Baseline 404 at 001 plus a wrong-Content-Type cold request at
    # 003: the verdict is the origin error and first_error stays 1 —
    # the later problem never rewrites the history (§6.3, §9.6).
    observations = healthy_observations()
    observations[0] = obs(1, "html", status=404, sentinel=False, before=0, after=1)
    observations[2] = obs(
        3, "html", status=500, cache="MISS", before=2, after=3
    )
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert result.first_error == 1


def test_origin_error_not_bleed_even_with_bleed_shaped_warm_pair():
    # Baseline broken AND a warm pair shaped exactly like a bleed:
    # §8.2 condition 1 forbids confirming the bleed, and the verdict
    # stays the origin error.
    observations = healthy_observations()
    observations[0] = obs(1, "html", status=404, sentinel=False, before=0, after=1)
    observations[4] = obs(5, "html", cache="MISS", before=4, after=5)
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="HIT",
        entry="entry-005",
        before=5,
        after=5,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 1


# ---------------------------------------------------------------------------
# §9.2 REPRESENTATION_BLEED
# ---------------------------------------------------------------------------


def bleed_observations(*, second_index=6):
    """Healthy run with one warm pair turned into a proven bleed:
    HTML first (MISS, entry-005), Markdown second (verified HIT of
    the same entry, HTML body, HTML Content-Type, no MD Sentinel)."""
    observations = healthy_observations()
    if second_index == 6:
        observations[4] = obs(5, "html", cache="MISS", before=4, after=5)
        observations[5] = obs(
            6,
            "markdown",
            content_type=HTML_CT,
            sentinel=False,
            cache="HIT",
            entry="entry-005",
            before=5,
            after=5,
            body=HTML_BODY,
        )
    else:
        observations[6] = obs(7, "markdown", cache="MISS", before=6, after=7)
        observations[7] = obs(
            8,
            "html",
            content_type=MD_CT,
            sentinel=False,
            cache="HIT",
            entry="entry-007",
            before=7,
            after=7,
            body=MD_BODY,
        )
    return observations


def test_bleed_html_to_markdown():
    result = classify(bleed_observations(second_index=6))
    assert result.verdict == "REPRESENTATION_BLEED"
    assert "REPRESENTATION_BLEED" in result.diagnostic_codes()
    assert "SENTINEL_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 6
    assert result.first_error_experiment_id == "HTML_TO_MARKDOWN"
    assert result.critical_count >= 1


def test_bleed_markdown_to_html():
    result = classify(bleed_observations(second_index=8))
    assert result.verdict == "REPRESENTATION_BLEED"
    assert result.first_error == 8
    assert result.first_error_experiment_id == "MARKDOWN_TO_HTML"


def test_bleed_has_no_policy_mismatch():
    # P2-4: a proven bleed is a HIT reusing a stored entry — the
    # policy check must not also fire. CACHE_POLICY_MISMATCH has no
    # business in a bleed run under either warm order.
    for second_index in (6, 8):
        result = classify(bleed_observations(second_index=second_index))
        assert result.verdict == "REPRESENTATION_BLEED"
        assert "CACHE_POLICY_MISMATCH" not in result.diagnostic_codes()


def test_bleed_not_when_second_revisits_origin():
    # HIT claimed but the counter moved: a conflict, never a bleed.
    # The wrong representation itself is still directly observed, so
    # the verdict is CONTRACT_MISMATCH (§9.6 step 4, before the
    # evidence-insufficient step 5) — but never REPRESENTATION_BLEED.
    observations = bleed_observations(second_index=6)
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="HIT",
        entry="entry-005",
        before=5,
        after=6,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert "CACHE_EVIDENCE_CONFLICT" in result.diagnostic_codes()
    assert result.first_error == 6


def test_bleed_not_when_entry_differs():
    observations = bleed_observations(second_index=6)
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="HIT",
        entry="entry-other",
        before=5,
        after=5,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    # The wrong representation is still a confirmed contract error.
    assert result.verdict == "CONTRACT_MISMATCH"
    assert result.first_error == 6


def test_bleed_not_when_first_request_was_bypass():
    observations = bleed_observations(second_index=6)
    observations[4] = obs(5, "html", cache="BYPASS", before=4, after=5)
    result = classify(observations)
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.verdict == "CONTRACT_MISMATCH"


def test_bleed_not_when_second_is_miss():
    # Same wrong body, but the second request went to the origin
    # (MISS): the origin served the wrong representation — that is
    # a contract mismatch, not a cache bleed.
    observations = bleed_observations(second_index=6)
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="MISS",
        before=5,
        after=6,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.verdict == "CONTRACT_MISMATCH"


def test_first_error_stays_earliest_despite_later_bleed():
    # A contract error at 003 plus a proven bleed at 006: the
    # verdict follows the §9.6 priority (bleed wins over a plain
    # contract error) but first_error stays 3 — severity never
    # re-orders history (§6.3).
    observations = bleed_observations(second_index=6)
    observations[2] = obs(3, "html", status=500, cache="MISS", before=2, after=3)
    result = classify(observations)
    assert result.verdict == "REPRESENTATION_BLEED"
    assert result.first_error == 3
    assert result.first_error_experiment_id == "HTML_COLD"


# ---------------------------------------------------------------------------
# §9.3 CONTRACT_MISMATCH
# ---------------------------------------------------------------------------


def test_contract_mismatch_proxy_wrong_content_type():
    observations = healthy_observations()
    observations[5] = obs(
        6, "markdown", content_type=HTML_CT, cache="MISS", before=5, after=6
    )
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CONTRACT_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 6


def test_contract_mismatch_proxy_status_error():
    observations = healthy_observations()
    observations[2] = obs(3, "html", status=500, cache="MISS", before=2, after=3)
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert result.first_error == 3


def test_contract_mismatch_warm_sentinel_error():
    # E24 shape: origin fine, warm response Sentinel wrong, cache
    # state fine — a contract mismatch, not a bleed.
    observations = healthy_observations()
    observations[5] = obs(
        6, "markdown", sentinel=False, cache="MISS", before=5, after=6
    )
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "SENTINEL_MISMATCH" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 6


def test_contract_mismatch_no_store_ignored():
    # C19 shape: no_store contract, but the proxy stored the response.
    observations = healthy_observations(cache_mode="no_store")
    observations[2] = obs(3, "html", cache="MISS", before=2, after=3)
    result = classify(observations, contract=build_contract(mode="no_store"))
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 3


def test_contract_mismatch_no_store_hit_reuses():
    observations = healthy_observations(cache_mode="no_store")
    observations[5] = obs(
        6,
        "markdown",
        cache="HIT",
        entry="entry-005",
        before=5,
        after=5,
        body=MD_BODY,
    )
    result = classify(observations, contract=build_contract(mode="no_store"))
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 6


def test_policy_mismatch_variant_cold_bypass():
    # P1-1 (§8.9 variant leg, §5.4/§6.1): a confirmed BYPASS under
    # variant_by_accept — the cache never stored anything, so
    # isolation was never exercised. Must be CONTRACT_MISMATCH via
    # CACHE_POLICY_MISMATCH, never a silent PASS.
    observations = healthy_observations()
    observations[2] = obs(3, "html", cache="BYPASS", before=2, after=3)
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 3
    diag = next(
        d for d in result.diagnostics if d.code == "CACHE_POLICY_MISMATCH"
    )
    assert diag.evidence["declared_cache_mode"] == "variant_by_accept"
    assert diag.evidence["observed_cache_status"] == "BYPASS"


def test_policy_mismatch_variant_warm_bypass():
    # P1-1, warm leg: the second warm request BYPASSes under a
    # variant contract — same policy violation, same verdict.
    observations = healthy_observations()
    observations[5] = obs(6, "markdown", cache="BYPASS", before=5, after=6)
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 6


def test_policy_mismatch_variant_bypass_not_when_state_unconfirmed():
    # An *unconfirmed* BYPASS is an evidence problem (§8.4), not a
    # proven policy violation: INCONCLUSIVE, no CACHE_POLICY_MISMATCH.
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=2, after=3,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_POLICY_MISMATCH" not in result.diagnostic_codes()
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()


def test_contract_mismatch_unexpected_cold_hit():
    # A HIT on a cold request after a confirmed reset contradicts
    # the cold-cache premise (§5.4).
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="HIT", entry="entry-stale", before=2, after=2
    )
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CONTRACT_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 3


# ---------------------------------------------------------------------------
# §9.4 INCONCLUSIVE — evidence insufficient, never a proven bleed
# ---------------------------------------------------------------------------


def test_inconclusive_when_cache_state_unknown():
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=2, after=3,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 3


def test_inconclusive_when_header_hit_conflicts_with_counter():
    # §8.8 / C22 shape: the representation itself is correct, but
    # the proxy says HIT while the origin counter moved +1 — the two
    # cache legs contradict each other, so the verdict is
    # INCONCLUSIVE, never a bleed (and no contract error exists to
    # outrank it under §9.6).
    observations = healthy_observations()
    observations[5] = obs(
        6,
        "markdown",
        cache="CACHE_STATE_UNKNOWN",
        key=None,
        entry=None,
        before=5,
        after=6,
    )
    raws = [
        raw(6, "markdown", cache_header="HIT", event_present=True)
    ]
    result = classify(observations, raw_observations=raws)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_EVIDENCE_CONFLICT" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()


def test_inconclusive_when_cache_header_missing():
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=2, after=3,
    )
    raws = [raw(3, "html", cache_header=None, event_present=True)]
    result = classify(observations, raw_observations=raws)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()
    assert "CACHE_EVIDENCE_CONFLICT" not in result.diagnostic_codes()


def test_inconclusive_when_reset_failed():
    failed = resets_ok()
    failed[0] = ResetEvidence(
        namespace="t006-html-cold",
        success=False,
        entries_before=2,
        entries_after=2,
        entries_removed=0,
    )
    result = classify(healthy_observations(), resets=failed)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()
    # The failure is run-level (no request violated the contract),
    # so there is no first error to point at.
    assert result.first_error is None


def test_inconclusive_when_no_reset_recorded():
    result = classify(healthy_observations(), resets=[])
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()


def test_inconclusive_when_observations_incomplete():
    result = classify(healthy_observations()[:7])
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()
    assert result.first_error is None


def test_inconclusive_when_contract_invalid():
    contract = build_contract()
    bad = dataclasses.replace(contract, url="http://example.com/doc")
    result = classify(healthy_observations(), contract=bad)
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()


def test_inconclusive_on_redirect():
    observations = healthy_observations()
    observations[5] = obs(
        6, "markdown", status=302, content_type="text/html",
        sentinel=False, cache="MISS", before=5, after=6,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()
    # A redirect is out of scope, not a contract mismatch or a bleed.
    assert "CONTRACT_MISMATCH" not in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 6


def test_inconclusive_on_oversize_body():
    observations = healthy_observations()
    raws = [raw(3, "html", body_size=2 * 1024 * 1024)]
    result = classify(observations, raw_observations=raws)
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()
    assert result.first_error == 3


def test_inconclusive_on_transport_error():
    observations = healthy_observations()
    observations[2] = obs(3, "html", status=0, cache=None, before=2, after=2)
    raws = [raw(3, "html", status=0, transport_error="ConnectionRefusedError")]
    result = classify(observations, raw_observations=raws)
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()


# ---------------------------------------------------------------------------
# "Only" rules — the negative guards of the task card
# ---------------------------------------------------------------------------


def test_vary_absent_alone_never_bleeds():
    # C03/C04 shape: no Vary anywhere, manual Accept keys, both
    # representations independently MISS — healthy, with only the
    # advisory WARNING kept.
    result = classify(
        healthy_observations(),
        vary_accept_present={1: False, 2: False},
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostic_codes() == (
        "VARY_ACCEPT_ABSENT",
        "VARY_ACCEPT_ABSENT",
    )
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    # An advisory WARNING is not a contract violation: no first error.
    assert result.first_error is None


def test_vary_present_no_warning():
    result = classify(
        healthy_observations(),
        vary_accept_present={1: True, 2: True},
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


def test_vary_required_missing_is_contract_mismatch_not_bleed():
    result = classify(
        healthy_observations(),
        contract=build_contract(vary_accept="required"),
        vary_accept_present={1: False, 2: False},
    )
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CONTRACT_MISMATCH" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 1


def test_vary_required_unknown_is_inconclusive_not_pass():
    # P2-1 fail-closed (§5.2, §9.6 step 5): vary_accept == "required"
    # but whether Vary is present is unknown — neither
    # raw_observations nor vary_accept_present was supplied — so the
    # required violation can neither be confirmed nor ruled out.
    # The run is INCONCLUSIVE, never a silent PASS.
    result = classify(
        healthy_observations(),
        contract=build_contract(vary_accept="required"),
    )
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()
    diag = next(
        d for d in result.diagnostics if d.code == "INCONCLUSIVE_LIMIT"
    )
    assert diag.evidence["limit_code"] == "vary_accept_unknown"
    assert result.first_error == 1


def test_vary_required_unknown_for_one_baseline_is_inconclusive():
    # Only one baseline's Vary is known (present): the other is
    # still unknown, so the run still fails closed.
    result = classify(
        healthy_observations(),
        contract=build_contract(vary_accept="required"),
        vary_accept_present={1: True},
    )
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()


def test_vary_required_known_present_passes():
    # Control: when the raw records show Vary: Accept on both
    # baselines, the required contract is satisfied and the run
    # passes — the fail-closed rule only fires on *unknown* Vary.
    raws = [
        raw(1, "html", headers={"Vary": "Accept"}),
        raw(2, "markdown", headers={"Vary": "Accept"}),
    ]
    result = classify(
        healthy_observations(),
        contract=build_contract(vary_accept="required"),
        raw_observations=raws,
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


def test_vary_absent_irrelevant_under_no_store():
    result = classify(
        healthy_observations(cache_mode="no_store"),
        contract=build_contract(mode="no_store"),
        vary_accept_present={1: False, 2: False},
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


def test_200_alone_never_passes():
    # Every status is 200 and every Sentinel matches, but the cache
    # evidence is missing: INCONCLUSIVE, never PASS.
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=2, after=3,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert result.verdict != "PASS_OBSERVED"


def test_sentinel_alone_never_proves_hit():
    # The warm second response matches its Sentinel, but its cache
    # state is unknown: no HIT is claimed and the run is
    # INCONCLUSIVE, not a pass and not a bleed.
    observations = healthy_observations()
    observations[5] = obs(
        6, "markdown", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=5, after=6,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()


def test_insufficient_evidence_never_becomes_proven_bleed():
    # A warm second with the wrong body but UNKNOWN cache state is
    # suspicious, not proven: CONTRACT_MISMATCH via the observed
    # Content-Type/Sentinel, never REPRESENTATION_BLEED.
    observations = healthy_observations()
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="CACHE_STATE_UNKNOWN",
        key=None,
        entry=None,
        before=5,
        after=6,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.verdict == "CONTRACT_MISMATCH"


# ---------------------------------------------------------------------------
# Origin-event cross-check
# ---------------------------------------------------------------------------


def matching_events(observations):
    """Origin events that genuinely match each observation: index
    equals the counter after the request, Accept and status match."""
    events = []
    for o in observations:
        events.append(
            OriginEvent(
                index=o.origin_counter_after,
                method="GET",
                path="/doc",
                accept="text/html"
                if o.requested_representation == "html"
                else "text/markdown",
                status=o.response_status,
                timestamp=0.0,
                received_at="2026-11-24T00:00:00Z",
            )
        )
    return events


def test_origin_events_matching_keeps_healthy_pass():
    observations = healthy_observations()
    result = classify(observations, events=matching_events(observations))
    assert result.verdict == "PASS_OBSERVED"


def test_origin_events_missing_downgrades_to_unknown():
    # The caller supplied an event log, but it holds no event for
    # the proxied requests: the behaviour leg is missing.
    result = classify(healthy_observations(), events=[])
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()


def test_none_means_skip_cross_check_not_confirmed():
    # P2-2, route B (ADR-002): origin_events=None / reset_evidence
    # =None mean "the caller declares this cross-check is not
    # performed" — the check is skipped, never treated as confirmed.
    # This meaning is reserved for unit tests; a production caller
    # (T007) must pass the real tuples and never pass None. The
    # contrast is [] (checked, found nothing) → INCONCLUSIVE, see
    # test_origin_events_missing_downgrades_to_unknown and
    # test_inconclusive_when_no_reset_recorded.
    result = classify(healthy_observations(), events=None, resets=None)
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


# ---------------------------------------------------------------------------
# Deterministic diagnostic ordering
# ---------------------------------------------------------------------------


def test_diagnostics_sorted_by_request_not_severity():
    result = classify(bleed_observations(second_index=6))
    indices = [
        d.request_index for d in result.diagnostics
        if d.request_index is not None
    ]
    assert indices == sorted(indices)
    # The bleed (CRITICAL, request 6) does not jump ahead of any
    # earlier diagnostic.
    assert result.diagnostics[0].request_index == 6


def test_repeat_classification_is_deterministic():
    first = classify(bleed_observations(second_index=6))
    second = classify(bleed_observations(second_index=6))
    assert first.as_dict() == second.as_dict()


# ---------------------------------------------------------------------------
# Live evidence: classify genuine T005 runs over loopback
# ---------------------------------------------------------------------------


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _live_contract():
    proxy_port = _free_port()
    origin_port = _free_port()
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = f"http://127.0.0.1:{proxy_port}/doc"
    data["origin_url"] = f"http://127.0.0.1:{origin_port}/doc"
    return parse_contract(data)


def test_live_healthy_run_classifies_pass():
    contract = _live_contract()
    run = run_experiments(
        contract, scenario="healthy", proxy_mode="respect_vary",
        namespace_prefix="t006-live",
    )
    result = classify_run(
        contract,
        run.observations,
        run.origin_events,
        run.reset_evidence,
        raw_observations=run.raw_observations,
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None


def test_live_bleed_run_classifies_bleed_at_request_6():
    contract = _live_contract()
    run = run_experiments(
        contract, scenario="healthy", proxy_mode="force_uri_only",
        namespace_prefix="t006-live",
    )
    result = classify_run(
        contract,
        run.observations,
        run.origin_events,
        run.reset_evidence,
        raw_observations=run.raw_observations,
    )
    assert result.verdict == "REPRESENTATION_BLEED"
    assert result.first_error == 6
    assert result.first_error_experiment_id == "HTML_TO_MARKDOWN"
    assert "REPRESENTATION_BLEED" in result.diagnostic_codes()


# ---------------------------------------------------------------------------
# T008: revalidation limit (§8.6, §11.3 E07/E08) and Vary:* BYPASS
# exemption (§8.9, §11.3 E03, ADR-004)
# ---------------------------------------------------------------------------


def _raws_with_cache_control(directive, *, vary="Accept", cache_header="MISS"):
    """Raw records for all 8 requests carrying one Cache-Control
    directive (baselines included) and the given Vary value."""
    raws = []
    for index, rep in (
        (1, "html"), (2, "markdown"), (3, "html"), (4, "markdown"),
        (5, "html"), (6, "markdown"), (7, "markdown"), (8, "html"),
    ):
        raws.append(
            raw(
                index,
                rep,
                cache_header=cache_header if index >= 3 else None,
                headers={"vary": vary, "cache-control": directive},
            )
        )
    return raws


def test_inconclusive_when_response_requires_revalidation_no_cache():
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control("no-cache"),
    )
    assert result.verdict == "INCONCLUSIVE"
    assert result.first_error == 1
    assert result.first_error_experiment_id == "ORIGIN_HTML"
    limits = [d for d in result.diagnostics if d.code == "INCONCLUSIVE_LIMIT"]
    assert len(limits) == 8
    assert {d.evidence["limit_code"] for d in limits} == {"revalidation_required"}


def test_inconclusive_when_response_requires_revalidation_max_age_zero():
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control("max-age=0"),
    )
    assert result.verdict == "INCONCLUSIVE"
    assert result.first_error == 1
    limits = [d for d in result.diagnostics if d.code == "INCONCLUSIVE_LIMIT"]
    assert len(limits) == 8
    assert {d.evidence["limit_code"] for d in limits} == {"revalidation_required"}


@pytest.mark.parametrize(
    "directive",
    [
        "max-age = 0",
        "max-age= 0",
        "max-age =0",
        'max-age="0"',
        "max-age = 0, public",
        'no-cache="field"',
        "no-cache=field",
        "No-Cache",
        "MAX-AGE = 0",
    ],
)
def test_revalidation_tolerant_parsing_t014(directive):
    """T014 (T008 P2-2): spaced / quoted revalidation directives
    trigger exactly like their compact forms (RFC 9111-tolerant)."""
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control(directive),
    )
    assert result.verdict == "INCONCLUSIVE"
    assert result.first_error == 1
    limits = [d for d in result.diagnostics if d.code == "INCONCLUSIVE_LIMIT"]
    assert len(limits) == 8
    assert {d.evidence["limit_code"] for d in limits} == {"revalidation_required"}


@pytest.mark.parametrize("directive", ["max-age=0.0", "max-age=", "max-age=60"])
def test_revalidation_non_trigger_forms_t014(directive):
    """T014 (T008 P2-2): invalid / fresh max-age values still pass."""
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control(directive),
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None


def test_fresh_max_age_does_not_require_revalidation():
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control("max-age=60"),
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None


def test_vary_star_bypass_passes_under_variant_contract():
    # E03 shape: every proxied request is a confirmed BYPASS, but
    # the responses carry Vary: *, so not storing them is compliant.
    result = classify(
        healthy_observations(cache_mode="no_store"),
        raw_observations=_raws_with_cache_control(
            "max-age=60", vary="*", cache_header="BYPASS"
        ),
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None
    assert "CACHE_POLICY_MISMATCH" not in result.diagnostic_codes()


def test_vary_accept_bypass_still_violates_variant_policy():
    # Same BYPASS run without Vary: * keeps the ADR-002 P1-1 rule.
    result = classify(
        healthy_observations(cache_mode="no_store"),
        raw_observations=_raws_with_cache_control(
            "max-age=60", vary="Accept", cache_header="BYPASS"
        ),
    )
    assert result.verdict == "CONTRACT_MISMATCH"
    assert result.first_error == 3
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
```

## tests/unit/test_contract.py

- SHA-256：`2be2ca5e76cc70eef82633fc941230aaeb06457fea7a6c55b09e98a58c071cd1`
- 字节数：10464

```
"""Unit tests for accepttwin.contract (T002 acceptance criteria).

Covers: legal contract passes; missing field rejected; duplicate Sentinel
rejected; non-loopback URL rejected (via contract); request headers outside
the whitelist rejected; contract hash repeat-consistent.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from accepttwin.contract import (
    Contract,
    ContractError,
    canonical_contract_hash,
    load_contract,
    parse_contract,
    validate_contract,
)
from accepttwin.schema import CONTRACT_SCHEMA

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "contracts" / "site.json"
SCHEMA_FILE = ROOT / "schemas" / "accepttwin.contract.v1.schema.json"

REQUIRED_TOP_LEVEL = [
    "schema",
    "contract_id",
    "name",
    "url",
    "origin_url",
    "representations",
    "request_headers",
    "cache_behavior",
    "limits",
    "metadata",
]


@pytest.fixture()
def valid_data() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture()
def valid_contract(valid_data: dict):
    return parse_contract(copy.deepcopy(valid_data))


def test_example_contract_loads():
    contract = load_contract(EXAMPLE)
    assert contract.schema == "accepttwin.contract/v1"
    assert contract.contract_id == "site-example-001"
    assert contract.url == "http://127.0.0.1:18765/doc"
    assert contract.origin_url == "http://127.0.0.1:18766/doc"
    assert contract.representations["html"].accept == "text/html"
    assert contract.representations["markdown"].accept == "text/markdown"
    assert contract.representations["html"].sentinel == "AT_HTML_SENTINEL_001"
    assert (
        contract.representations["markdown"].sentinel
        == "AT_MARKDOWN_SENTINEL_001"
    )
    assert contract.cache_behavior["mode"] == "variant_by_accept"
    assert contract.limits["max_body_bytes"] == 1048576
    assert validate_contract(contract).ok


def test_valid_dict_parses(valid_data):
    contract = parse_contract(valid_data)
    assert contract.name.startswith("Example site")
    assert validate_contract(contract).ok


def test_schema_file_matches_module():
    on_disk = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert on_disk == CONTRACT_SCHEMA


@pytest.mark.parametrize("field", REQUIRED_TOP_LEVEL)
def test_missing_top_level_field_rejected(valid_data, field):
    del valid_data[field]
    with pytest.raises(ContractError, match="missing required field"):
        parse_contract(valid_data)


def test_missing_nested_field_rejected(valid_data):
    del valid_data["representations"]["html"]["sentinel"]
    with pytest.raises(ContractError, match="missing required field"):
        parse_contract(valid_data)


def test_unknown_top_level_field_rejected(valid_data):
    valid_data["surprise"] = True
    with pytest.raises(ContractError, match="unsupported field"):
        parse_contract(valid_data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["representations"]["html"].update({"extra": 1}),
        lambda d: d["representations"].update({"text": {}}),
        lambda d: d["cache_behavior"].update({"unknown_mode": "x"}),
        lambda d: d["request_headers"].update({"cookie": "abc"}),
        lambda d: d["limits"].update({"max_redirects": 3}),
    ],
)
def test_unknown_nested_field_rejected(valid_data, mutate):
    mutate(valid_data)
    with pytest.raises(ContractError, match="unsupported field"):
        parse_contract(valid_data)


def test_duplicate_sentinel_rejected(valid_data):
    valid_data["representations"]["markdown"]["sentinel"] = (
        valid_data["representations"]["html"]["sentinel"]
    )
    with pytest.raises(ContractError, match="must be different"):
        parse_contract(valid_data)


def test_sentinel_with_whitespace_rejected(valid_data):
    valid_data["representations"]["html"]["sentinel"] = "AT HTML SENTINEL"
    with pytest.raises(ContractError, match="whitespace"):
        parse_contract(valid_data)


@pytest.mark.parametrize(
    "rep,field,value",
    [
        ("html", "accept", "text/plain"),
        ("html", "accept", "text/markdown"),
        ("markdown", "accept", "text/html"),
        ("markdown", "accept", "text/markdown; charset=utf-8"),
        ("html", "expected_status", 404),
        ("markdown", "expected_status", 200.5),
        ("html", "expected_content_type", "text/html"),
        ("markdown", "expected_content_type", "text/html; charset=utf-8"),
    ],
)
def test_frozen_representation_value_rejected(valid_data, rep, field, value):
    valid_data["representations"][rep][field] = value
    with pytest.raises(ContractError):
        parse_contract(valid_data)


def test_public_url_rejected(valid_data):
    valid_data["url"] = "http://93.184.216.34:18765/doc"
    with pytest.raises(ContractError, match="non-loopback"):
        parse_contract(valid_data)


def test_public_origin_url_rejected(valid_data):
    valid_data["origin_url"] = "http://93.184.216.34:18766/doc"
    with pytest.raises(ContractError, match="non-loopback"):
        parse_contract(valid_data)


def test_https_url_rejected(valid_data):
    valid_data["url"] = "https://127.0.0.1:18765/doc"
    with pytest.raises(ContractError, match="only 'http'"):
        parse_contract(valid_data)


def test_url_origin_path_mismatch_rejected(valid_data):
    valid_data["origin_url"] = "http://127.0.0.1:18766/other"
    with pytest.raises(ContractError, match="same path"):
        parse_contract(valid_data)


def test_url_origin_same_port_rejected(valid_data):
    valid_data["origin_url"] = "http://127.0.0.1:18765/doc"
    with pytest.raises(ContractError, match="different ports"):
        parse_contract(valid_data)


def test_no_store_with_max_age_rejected(valid_data):
    valid_data["cache_behavior"] = {
        "mode": "no_store",
        "vary_accept": "not_required",
        "max_age_seconds": 60,
    }
    with pytest.raises(ContractError, match="no_store"):
        parse_contract(valid_data)


def test_no_store_contract_valid(valid_data):
    valid_data["cache_behavior"] = {
        "mode": "no_store",
        "vary_accept": "not_required",
        "max_age_seconds": None,
    }
    contract = parse_contract(valid_data)
    assert contract.cache_behavior["mode"] == "no_store"
    assert validate_contract(contract).ok


def test_unknown_cache_mode_rejected(valid_data):
    valid_data["cache_behavior"]["mode"] = "force_uri_only"
    with pytest.raises(ContractError):
        parse_contract(valid_data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_agent", "curl/8.0"),
        ("accept_encoding", "gzip"),
        ("accept_language", "fr"),
    ],
)
def test_fixed_request_header_value_rejected(valid_data, field, value):
    valid_data["request_headers"][field] = value
    with pytest.raises(ContractError):
        parse_contract(valid_data)


def test_cookie_in_request_headers_rejected(valid_data):
    # Unknown header names are rejected by the schema (additionalProperties)
    # and would also fail the whitelist check; either way it must fail.
    valid_data["request_headers"]["cookie"] = "session=abc"
    with pytest.raises(ContractError, match="unsupported field"):
        parse_contract(valid_data)


def test_limits_over_1mib_rejected(valid_data):
    valid_data["limits"]["max_body_bytes"] = 1048577
    with pytest.raises(ContractError):
        parse_contract(valid_data)


def test_metadata_free_form_allowed(valid_data):
    valid_data["metadata"] = {"anything": [1, 2, {"goes": True}]}
    contract = parse_contract(valid_data)
    assert validate_contract(contract).ok


def test_defaults_applied(valid_data):
    del valid_data["cache_behavior"]["vary_accept"]
    del valid_data["cache_behavior"]["max_age_seconds"]
    del valid_data["limits"]["max_body_bytes"]
    del valid_data["limits"]["request_timeout_seconds"]
    contract = parse_contract(valid_data)
    assert contract.cache_behavior["vary_accept"] == "advisory"
    assert contract.cache_behavior["max_age_seconds"] is None
    assert contract.limits["max_body_bytes"] == 1048576
    assert contract.limits["request_timeout_seconds"] == 5.0


def test_missing_file_rejected():
    with pytest.raises(ContractError, match="cannot read"):
        load_contract(ROOT / "contracts" / "does-not-exist.json")


def test_malformed_json_file_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContractError, match="not valid JSON"):
        load_contract(bad)


def test_duplicate_json_key_rejected(tmp_path):
    dup = tmp_path / "dup.json"
    dup.write_text('{"schema": "a", "schema": "b"}', encoding="utf-8")
    with pytest.raises(ContractError, match="duplicate JSON key"):
        load_contract(dup)


def test_validate_contract_reports_errors(valid_data):
    # Build an unchecked Contract directly and prove validate_contract
    # catches it instead of trusting the constructor.
    bad = parse_contract(copy.deepcopy(valid_data))
    object.__setattr__(bad, "url", "http://93.184.216.34:18765/doc")
    result = validate_contract(bad)
    assert not result.ok
    assert any("non-loopback" in err for err in result.errors)


def test_validate_contract_rejects_non_contract():
    result = validate_contract("not a contract")  # type: ignore[arg-type]
    assert not result.ok


def test_contract_hash_repeat_consistent(valid_contract):
    first = canonical_contract_hash(valid_contract)
    assert re.fullmatch(r"[0-9a-f]{64}", first)
    assert canonical_contract_hash(valid_contract) == first
    # A second, independently parsed instance hashes identically.
    second = load_contract(EXAMPLE)
    assert canonical_contract_hash(second) == first


def test_contract_hash_key_order_independent(valid_data):
    forward = parse_contract(copy.deepcopy(valid_data))
    # Serialise with keys sorted and re-parse: same hash.
    sorted_keys_json = json.dumps(valid_data, sort_keys=True, indent=2)
    reparsed = parse_contract(json.loads(sorted_keys_json))
    assert canonical_contract_hash(reparsed) == canonical_contract_hash(forward)


def test_contract_hash_changes_when_input_changes(valid_data, valid_contract):
    valid_data["representations"]["html"]["sentinel"] = "AT_HTML_SENTINEL_002"
    changed = parse_contract(valid_data)
    assert canonical_contract_hash(changed) != canonical_contract_hash(
        valid_contract
    )
```

## tests/unit/test_diagnostics.py

- SHA-256：`a8129cdc7ce1398c30833c7d23d69d287375bcd85a428d0421c07f152433d1c7`
- 字节数：33371

```
"""Unit tests for the frozen diagnostic codes (P032 T006).

Covers PROJECT_BOOK §8 (all nine codes, each with at least one
positive and one negative test), §8 severity mapping, and the
deterministic ordering of §6.3 / §7.8 I-08.

These tests exercise :mod:`accepttwin.diagnostics` in isolation —
pure predicates over already-measured evidence, no I/O, no HTTP.
The end-to-end behaviour (verdicts, first-error location) is
covered in ``test_classifier.py``.
"""

from __future__ import annotations

import pytest

from accepttwin.diagnostics import (
    CODE_SEVERITY,
    DIAGNOSTIC_CODES,
    Diagnostic,
    check_bleed,
    check_cache_state,
    check_contract_response,
    check_inconclusive_limit,
    check_no_store_policy,
    check_origin_baseline,
    check_reset_evidence,
    check_sentinel,
    check_unexpected_hit,
    check_variant_by_accept_policy,
    check_vary,
    diagnostic_order,
    make_diagnostic,
    sort_diagnostics,
)
from accepttwin.cache_proxy import ResetEvidence

HTML_BODY = "h" * 64
MD_BODY = "m" * 64
HTML_SENTINEL_SHA = "a" * 64
MD_SENTINEL_SHA = "b" * 64
KEY_1 = "k" * 64
KEY_2 = "j" * 64
ENTRY_1 = "entry-aaa"
ENTRY_2 = "entry-bbb"

HTML_CT = "text/html; charset=utf-8"
MD_CT = "text/markdown; charset=utf-8"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def baseline_kwargs(**overrides):
    kwargs = {
        "request_index": 1,
        "experiment_id": "ORIGIN_HTML",
        "requested_representation": "html",
        "response_status": 200,
        "response_content_type": HTML_CT,
        "sentinel_match": True,
        "expected_status": 200,
        "expected_content_type": HTML_CT,
        "expected_sentinel_sha256": HTML_SENTINEL_SHA,
        "body_sha256": HTML_BODY,
    }
    kwargs.update(overrides)
    return kwargs


def bleed_kwargs(**overrides):
    """A complete §8.2 chain: HTML first (MISS), Markdown second (HIT
    of the same entry, HTML body, HTML Content-Type, no MD Sentinel)."""
    kwargs = {
        "first_request_index": 5,
        "second_request_index": 6,
        "experiment_id": "HTML_TO_MARKDOWN",
        "baseline_correct": True,
        "first_correct": True,
        "first_cache_status": "MISS",
        "first_cache_entry_id": ENTRY_1,
        "first_body_sha256": HTML_BODY,
        "second_cache_status": "HIT",
        "second_cache_entry_id": ENTRY_1,
        "second_cache_key_sha256": KEY_1,
        "second_body_sha256": HTML_BODY,
        "second_response_content_type": HTML_CT,
        "second_origin_counter_before": 5,
        "second_origin_counter_after": 5,
        "second_origin_counter_delta": 0,
        "second_sentinel_match": False,
        "first_expected_content_type": HTML_CT,
        "requested_representation": "markdown",
    }
    kwargs.update(overrides)
    return kwargs


def cache_state_kwargs(**overrides):
    kwargs = {
        "request_index": 3,
        "experiment_id": "HTML_COLD",
        "cache_status": "MISS",
        "origin_counter_delta": 1,
        "cache_key_sha256": KEY_1,
        "cache_entry_id": ENTRY_1,
        "header_status": "MISS",
        "origin_event_present": True,
    }
    kwargs.update(overrides)
    return kwargs


def reset_ok(namespace="t006-html-cold"):
    return ResetEvidence(
        namespace=namespace,
        success=True,
        entries_before=1,
        entries_after=0,
        entries_removed=1,
    )


# ---------------------------------------------------------------------------
# §8.0 — code table and severity mapping
# ---------------------------------------------------------------------------


def test_nine_codes_in_spec_order():
    assert DIAGNOSTIC_CODES == (
        "ORIGIN_NEGOTIATION_ERROR",
        "REPRESENTATION_BLEED",
        "CONTRACT_MISMATCH",
        "CACHE_STATE_UNKNOWN",
        "SENTINEL_MISMATCH",
        "INCONCLUSIVE_LIMIT",
        "VARY_ACCEPT_ABSENT",
        "CACHE_EVIDENCE_CONFLICT",
        "CACHE_POLICY_MISMATCH",
    )


def test_severities_are_only_critical_or_warning():
    assert set(CODE_SEVERITY) == set(DIAGNOSTIC_CODES)
    assert set(CODE_SEVERITY.values()) <= {"CRITICAL", "WARNING"}
    assert CODE_SEVERITY["ORIGIN_NEGOTIATION_ERROR"] == "CRITICAL"
    assert CODE_SEVERITY["REPRESENTATION_BLEED"] == "CRITICAL"
    assert CODE_SEVERITY["CONTRACT_MISMATCH"] == "CRITICAL"
    assert CODE_SEVERITY["CACHE_STATE_UNKNOWN"] == "WARNING"
    assert CODE_SEVERITY["SENTINEL_MISMATCH"] == "CRITICAL"
    assert CODE_SEVERITY["INCONCLUSIVE_LIMIT"] == "WARNING"
    assert CODE_SEVERITY["VARY_ACCEPT_ABSENT"] == "WARNING"
    assert CODE_SEVERITY["CACHE_EVIDENCE_CONFLICT"] == "WARNING"
    assert CODE_SEVERITY["CACHE_POLICY_MISMATCH"] == "CRITICAL"


def test_make_diagnostic_rejects_unknown_code():
    with pytest.raises(ValueError, match="unknown diagnostic code"):
        make_diagnostic("NOT_A_CODE", "boom")


def test_diagnostic_rejects_wrong_severity():
    with pytest.raises(ValueError, match="must have severity"):
        Diagnostic(
            code="VARY_ACCEPT_ABSENT",
            severity="CRITICAL",
            message="Vary is only ever a WARNING",
        )


def test_diagnostic_rejects_blank_message():
    with pytest.raises(ValueError, match="must not be blank"):
        make_diagnostic("CACHE_STATE_UNKNOWN", "   ")


def test_diagnostic_rejects_body_text_evidence():
    # §7.12 I-12: raw body text must never enter a diagnostic.
    with pytest.raises(ValueError, match="must not contain"):
        make_diagnostic(
            "SENTINEL_MISMATCH",
            "sentinel missing",
            evidence={"body_text": "<html>secret</html>"},
        )


def test_diagnostic_as_dict_round_trip():
    diag = make_diagnostic(
        "CACHE_STATE_UNKNOWN",
        "unknown",
        experiment_id="HTML_COLD",
        request_index=3,
        evidence={"cache_status": "CACHE_STATE_UNKNOWN"},
    )
    data = diag.as_dict()
    assert data["code"] == "CACHE_STATE_UNKNOWN"
    assert data["severity"] == "WARNING"
    assert data["request_index"] == 3
    assert "body_text" not in data["evidence"]


# ---------------------------------------------------------------------------
# §8.1 ORIGIN_NEGOTIATION_ERROR
# ---------------------------------------------------------------------------


def test_origin_error_on_404_baseline():
    diag = check_origin_baseline(**baseline_kwargs(response_status=404))
    assert diag is not None
    assert diag.code == "ORIGIN_NEGOTIATION_ERROR"
    assert diag.severity == "CRITICAL"
    assert diag.request_index == 1
    assert diag.evidence["origin_direct"] is True
    assert diag.evidence["observed_status"] == 404


def test_origin_error_on_wrong_content_type():
    diag = check_origin_baseline(
        **baseline_kwargs(response_content_type="text/plain")
    )
    assert diag is not None
    assert diag.code == "ORIGIN_NEGOTIATION_ERROR"


def test_origin_error_on_missing_sentinel():
    diag = check_origin_baseline(**baseline_kwargs(sentinel_match=False))
    assert diag is not None
    assert diag.code == "ORIGIN_NEGOTIATION_ERROR"


def test_origin_no_error_when_baseline_correct():
    assert check_origin_baseline(**baseline_kwargs()) is None


def test_origin_no_error_when_only_cache_would_differ():
    # A correct baseline is never an origin error, even if the
    # caller worries about the cache: §8.1 is about the origin only.
    assert check_origin_baseline(**baseline_kwargs()) is None


# ---------------------------------------------------------------------------
# §8.2 REPRESENTATION_BLEED
# ---------------------------------------------------------------------------


def test_bleed_on_full_evidence_chain():
    diag = check_bleed(**bleed_kwargs())
    assert diag is not None
    assert diag.code == "REPRESENTATION_BLEED"
    assert diag.severity == "CRITICAL"
    assert diag.request_index == 6
    assert diag.evidence["cache_status"] == "HIT"
    assert diag.evidence["cache_entry_id"] == ENTRY_1
    assert diag.evidence["origin_counter_delta"] == 0
    assert diag.evidence["body_sha256"] == HTML_BODY


def test_bleed_not_when_baseline_wrong():
    assert check_bleed(**bleed_kwargs(baseline_correct=False)) is None


def test_bleed_not_when_first_request_wrong():
    assert check_bleed(**bleed_kwargs(first_correct=False)) is None


def test_bleed_not_when_first_request_bypass():
    # A BYPASS stores nothing, so a later HIT cannot reuse its entry.
    assert check_bleed(**bleed_kwargs(first_cache_status="BYPASS")) is None


def test_bleed_not_when_second_is_miss():
    assert check_bleed(**bleed_kwargs(second_cache_status="MISS")) is None


def test_bleed_not_when_origin_revisited():
    assert check_bleed(**bleed_kwargs(second_origin_counter_delta=1)) is None


def test_bleed_not_when_entry_differs():
    assert (
        check_bleed(**bleed_kwargs(second_cache_entry_id=ENTRY_2)) is None
    )


def test_bleed_not_when_entry_id_missing():
    assert (
        check_bleed(**bleed_kwargs(second_cache_entry_id=None)) is None
    )


def test_bleed_not_when_body_differs():
    assert check_bleed(**bleed_kwargs(second_body_sha256=MD_BODY)) is None


def test_bleed_not_when_content_type_is_correct():
    assert (
        check_bleed(**bleed_kwargs(second_response_content_type=MD_CT))
        is None
    )


def test_bleed_not_when_sentinel_matches():
    assert check_bleed(**bleed_kwargs(second_sentinel_match=True)) is None


# ---------------------------------------------------------------------------
# §8.3 CONTRACT_MISMATCH (status / Content-Type leg)
# ---------------------------------------------------------------------------


def test_contract_mismatch_on_wrong_status():
    diag = check_contract_response(
        request_index=3,
        experiment_id="HTML_COLD",
        requested_representation="html",
        response_status=500,
        response_content_type=HTML_CT,
        cache_status="MISS",
        sentinel_match=True,
        expected_status=200,
        expected_content_type=HTML_CT,
    )
    assert diag is not None
    assert diag.code == "CONTRACT_MISMATCH"
    assert diag.severity == "CRITICAL"


def test_contract_mismatch_on_wrong_content_type():
    diag = check_contract_response(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        requested_representation="markdown",
        response_status=200,
        response_content_type="text/html",
        cache_status="MISS",
        sentinel_match=True,
        expected_status=200,
        expected_content_type=MD_CT,
    )
    assert diag is not None
    assert diag.code == "CONTRACT_MISMATCH"


def test_contract_no_mismatch_when_response_correct():
    assert (
        check_contract_response(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            response_status=200,
            response_content_type=HTML_CT,
            cache_status="MISS",
            sentinel_match=True,
            expected_status=200,
            expected_content_type=HTML_CT,
        )
        is None
    )


def test_contract_no_mismatch_on_redirect():
    # Redirects are out of scope (§8.6), not contract mismatches.
    assert (
        check_contract_response(
            request_index=6,
            experiment_id="HTML_TO_MARKDOWN",
            requested_representation="markdown",
            response_status=302,
            response_content_type="text/html",
            cache_status="MISS",
            sentinel_match=False,
            expected_status=200,
            expected_content_type=MD_CT,
        )
        is None
    )


def test_contract_no_mismatch_on_sentinel_only():
    # A lone Sentinel failure is §8.5's job, not §8.3's.
    assert (
        check_contract_response(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            response_status=200,
            response_content_type=HTML_CT,
            cache_status="MISS",
            sentinel_match=False,
            expected_status=200,
            expected_content_type=HTML_CT,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.4 CACHE_STATE_UNKNOWN / §8.8 CACHE_EVIDENCE_CONFLICT
# ---------------------------------------------------------------------------


def test_cache_unknown_when_verified_state_unknown():
    diag = check_cache_state(**cache_state_kwargs(cache_status="CACHE_STATE_UNKNOWN"))
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"
    assert diag.severity == "WARNING"


def test_cache_unknown_when_no_state_at_all():
    # A proxied request carrying None has no cache evidence (§8.4).
    diag = check_cache_state(**cache_state_kwargs(cache_status=None))
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_cache_unknown_when_key_header_missing():
    diag = check_cache_state(
        **cache_state_kwargs(cache_status="MISS", cache_key_sha256=None)
    )
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_cache_unknown_when_origin_event_missing():
    diag = check_cache_state(
        **cache_state_kwargs(cache_status="MISS", origin_event_present=False)
    )
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_cache_conflict_hit_with_origin_revisit():
    # Header HIT but the origin counter moved: §8.8, never a bleed.
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="HIT", origin_counter_delta=1, header_status="HIT"
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_EVIDENCE_CONFLICT"
    assert diag.severity == "WARNING"
    assert diag.evidence["evidence_consistent"] is False


def test_cache_conflict_miss_without_origin_revisit():
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="MISS", origin_counter_delta=0, header_status="MISS"
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_EVIDENCE_CONFLICT"


def test_cache_conflict_unknown_state_with_contradicting_header():
    # Verified UNKNOWN + a raw header HIT contradicted by delta +1.
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="CACHE_STATE_UNKNOWN",
            origin_counter_delta=1,
            header_status="HIT",
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_EVIDENCE_CONFLICT"


def test_cache_state_evidence_carries_section_84_fields():
    # P2-3 (§8.4): UNKNOWN diagnostics carry proxy_cache_header_
    # present, origin_journal_available, cache_reset_confirmed and
    # evidence_conflict — None where the leg was not supplied.
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="CACHE_STATE_UNKNOWN",
            cache_reset_confirmed=True,
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"
    assert diag.evidence["proxy_cache_header_present"] is True
    assert diag.evidence["origin_journal_available"] is True
    assert diag.evidence["cache_reset_confirmed"] is True
    assert diag.evidence["evidence_conflict"] is False


def test_cache_state_evidence_conflict_flag_is_true_on_conflict():
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="HIT",
            origin_counter_delta=1,
            header_status="HIT",
            cache_reset_confirmed=True,
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_EVIDENCE_CONFLICT"
    assert diag.evidence["evidence_conflict"] is True
    assert diag.evidence["evidence_consistent"] is False
    assert diag.evidence["cache_reset_confirmed"] is True


def test_cache_state_evidence_fields_unknown_when_not_supplied():
    # A leg that was never supplied stays None (unknown), never a
    # guessed False.
    diag = check_cache_state(
        request_index=3,
        experiment_id="HTML_COLD",
        cache_status="CACHE_STATE_UNKNOWN",
        origin_counter_delta=1,
        cache_key_sha256=None,
        cache_entry_id=None,
        header_status=None,
        origin_event_present=None,
    )
    assert diag is not None
    assert diag.evidence["proxy_cache_header_present"] is None
    assert diag.evidence["origin_journal_available"] is None
    assert diag.evidence["cache_reset_confirmed"] is None


def test_cache_no_diagnostic_when_miss_confirmed():
    assert check_cache_state(**cache_state_kwargs()) is None


def test_cache_no_diagnostic_when_hit_confirmed():
    assert (
        check_cache_state(
            **cache_state_kwargs(
                cache_status="HIT",
                origin_counter_delta=0,
                header_status="HIT",
            )
        )
        is None
    )


def test_cache_no_diagnostic_when_bypass_confirmed():
    assert (
        check_cache_state(
            **cache_state_kwargs(
                cache_status="BYPASS",
                cache_key_sha256=None,
                cache_entry_id=None,
                header_status="BYPASS",
            )
        )
        is None
    )


def test_cache_no_conflict_when_header_matches_verified_state():
    assert (
        check_cache_state(
            **cache_state_kwargs(cache_status="MISS", header_status="MISS")
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.5 SENTINEL_MISMATCH
# ---------------------------------------------------------------------------


def test_sentinel_mismatch_when_sentinel_absent():
    diag = check_sentinel(
        request_index=3,
        experiment_id="HTML_COLD",
        requested_representation="html",
        sentinel_match=False,
        response_content_type=HTML_CT,
        expected_sentinel_sha256=HTML_SENTINEL_SHA,
        body_sha256=MD_BODY,
    )
    assert diag is not None
    assert diag.code == "SENTINEL_MISMATCH"
    assert diag.severity == "CRITICAL"
    assert diag.evidence["sentinel_match"] is False
    assert diag.evidence["body_sha256"] == MD_BODY


def test_sentinel_no_mismatch_when_sentinel_present():
    assert (
        check_sentinel(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            sentinel_match=True,
            response_content_type=HTML_CT,
            expected_sentinel_sha256=HTML_SENTINEL_SHA,
            body_sha256=HTML_BODY,
        )
        is None
    )


def test_sentinel_no_mismatch_when_only_status_wrong():
    # A wrong status with a matching Sentinel is not a Sentinel
    # problem; §8.3 covers the status.
    assert (
        check_sentinel(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            sentinel_match=True,
            response_content_type=HTML_CT,
            expected_sentinel_sha256=HTML_SENTINEL_SHA,
            body_sha256=HTML_BODY,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.6 INCONCLUSIVE_LIMIT
# ---------------------------------------------------------------------------


def test_inconclusive_limit_on_redirect():
    diag = check_inconclusive_limit(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        limit_code="redirect",
        response_status=302,
        detail="status 302 (redirects are not followed in this release)",
    )
    assert diag is not None
    assert diag.code == "INCONCLUSIVE_LIMIT"
    assert diag.severity == "WARNING"
    assert diag.evidence["limit_code"] == "redirect"
    assert diag.evidence["response_status"] == 302


def test_inconclusive_limit_on_oversize_body():
    diag = check_inconclusive_limit(
        request_index=3,
        experiment_id="HTML_COLD",
        limit_code="body_too_large",
        body_size=2 * 1024 * 1024,
        supported_limit=1024 * 1024,
    )
    assert diag is not None
    assert diag.code == "INCONCLUSIVE_LIMIT"
    assert diag.evidence["body_size"] == 2 * 1024 * 1024


def test_inconclusive_limit_none_when_no_limit_hit():
    assert (
        check_inconclusive_limit(
            request_index=3,
            experiment_id="HTML_COLD",
            limit_code="",
        )
        is None
    )


def test_inconclusive_limit_carries_request_url_when_supplied():
    # P2-3 (§8.6): request_url is recorded when the caller has a
    # raw record; it is absent (not guessed) when not supplied.
    diag = check_inconclusive_limit(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        limit_code="redirect",
        response_status=302,
        request_url="http://127.0.0.1:18765/doc",
        redirect_target="http://127.0.0.1:18765/other",
    )
    assert diag is not None
    assert diag.evidence["request_url"] == "http://127.0.0.1:18765/doc"
    assert diag.evidence["redirect_target"] == "http://127.0.0.1:18765/other"
    plain = check_inconclusive_limit(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        limit_code="redirect",
        response_status=302,
    )
    assert plain is not None
    assert "request_url" not in plain.evidence
    assert "redirect_target" not in plain.evidence


# ---------------------------------------------------------------------------
# §8.7 VARY_ACCEPT_ABSENT
# ---------------------------------------------------------------------------


def test_vary_warning_when_absent_and_advisory():
    diag = check_vary(
        request_index=1,
        experiment_id="ORIGIN_HTML",
        requested_representation="html",
        vary_accept_present=False,
        vary_accept_required=False,
        cacheable=True,
    )
    assert diag is not None
    assert diag.code == "VARY_ACCEPT_ABSENT"
    assert diag.severity == "WARNING"


def test_vary_absent_when_required_is_contract_mismatch():
    # §5.2: required + absent is a contract violation — but still
    # never a bleed (I-11).
    diag = check_vary(
        request_index=1,
        experiment_id="ORIGIN_HTML",
        requested_representation="html",
        vary_accept_present=False,
        vary_accept_required=True,
        cacheable=True,
    )
    assert diag is not None
    assert diag.code == "CONTRACT_MISMATCH"
    assert diag.severity == "CRITICAL"


def test_vary_no_diagnostic_when_present():
    assert (
        check_vary(
            request_index=1,
            experiment_id="ORIGIN_HTML",
            requested_representation="html",
            vary_accept_present=True,
            vary_accept_required=False,
            cacheable=True,
        )
        is None
    )


def test_vary_no_diagnostic_when_not_cacheable():
    # no_store: Vary is not required and its absence means nothing.
    assert (
        check_vary(
            request_index=1,
            experiment_id="ORIGIN_HTML",
            requested_representation="html",
            vary_accept_present=False,
            vary_accept_required=False,
            cacheable=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.9 CACHE_POLICY_MISMATCH (no_store leg)
# ---------------------------------------------------------------------------


def test_policy_mismatch_when_no_store_miss():
    diag = check_no_store_policy(
        request_index=3,
        experiment_id="HTML_COLD",
        cache_status="MISS",
        cache_entry_count_before=0,
        cache_entry_count_after=1,
    )
    assert diag is not None
    assert diag.code == "CACHE_POLICY_MISMATCH"
    assert diag.severity == "CRITICAL"
    assert diag.evidence["declared_cache_mode"] == "no_store"
    assert diag.evidence["observed_cache_status"] == "MISS"


def test_policy_mismatch_when_no_store_hit():
    diag = check_no_store_policy(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        cache_status="HIT",
    )
    assert diag is not None
    assert diag.code == "CACHE_POLICY_MISMATCH"


def test_policy_no_mismatch_when_bypass():
    assert (
        check_no_store_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="BYPASS",
        )
        is None
    )


def test_policy_no_mismatch_when_state_unknown():
    # Storage cannot be proven from an unconfirmed state.
    assert (
        check_no_store_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="CACHE_STATE_UNKNOWN",
        )
        is None
    )


def test_policy_no_mismatch_when_no_state():
    assert (
        check_no_store_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status=None,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.9 CACHE_POLICY_MISMATCH (variant_by_accept leg, P1-1)
# ---------------------------------------------------------------------------


def test_variant_policy_mismatch_when_bypass():
    diag = check_variant_by_accept_policy(
        request_index=3,
        experiment_id="HTML_COLD",
        cache_status="BYPASS",
        cache_entry_count_before=0,
        cache_entry_count_after=0,
    )
    assert diag is not None
    assert diag.code == "CACHE_POLICY_MISMATCH"
    assert diag.severity == "CRITICAL"
    assert diag.request_index == 3
    assert diag.evidence["declared_cache_mode"] == "variant_by_accept"
    assert diag.evidence["observed_cache_status"] == "BYPASS"
    assert diag.evidence["cache_entry_count_before"] == 0
    assert diag.evidence["cache_entry_count_after"] == 0


def test_variant_policy_no_mismatch_when_miss_or_hit():
    # MISS and HIT are the mode's normal states, not violations.
    assert (
        check_variant_by_accept_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="MISS",
        )
        is None
    )
    assert (
        check_variant_by_accept_policy(
            request_index=6,
            experiment_id="HTML_TO_MARKDOWN",
            cache_status="HIT",
        )
        is None
    )


def test_variant_policy_no_mismatch_when_state_unknown_or_absent():
    # An unconfirmed BYPASS is an evidence problem (§8.4), never a
    # proven policy violation — the caller must pass only the
    # confirmed state.
    assert (
        check_variant_by_accept_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="CACHE_STATE_UNKNOWN",
        )
        is None
    )
    assert (
        check_variant_by_accept_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status=None,
        )
        is None
    )


def test_variant_policy_exempt_when_vary_star():
    # T008 (ADR-004, §11.3 E03): Vary: * forbids reuse (RFC 9111
    # §4.1), so a BYPASS there is compliant, not a policy violation.
    for vary in ("*", "Accept, *", "*, Accept-Encoding"):
        assert (
            check_variant_by_accept_policy(
                request_index=3,
                experiment_id="HTML_COLD",
                cache_status="BYPASS",
                cache_entry_count_before=0,
                cache_entry_count_after=0,
                vary=vary,
            )
            is None
        )


def test_variant_policy_still_fires_without_vary_star():
    # No Vary at all, or a Vary without *, keeps the P1-1 rule: a
    # confirmed BYPASS under variant_by_accept is a violation.
    for vary in (None, "Accept", "Accept, Accept-Encoding"):
        diag = check_variant_by_accept_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="BYPASS",
            cache_entry_count_before=0,
            cache_entry_count_after=0,
            vary=vary,
        )
        assert diag is not None
        assert diag.code == "CACHE_POLICY_MISMATCH"


# ---------------------------------------------------------------------------
# §8.3 unexpected-HIT leg (cold-cache premise)
# ---------------------------------------------------------------------------


def test_unexpected_hit_on_cold_request():
    diag = check_unexpected_hit(
        request_index=3,
        experiment_id="HTML_COLD",
        requested_representation="html",
        cache_status="HIT",
        response_status=200,
        response_content_type=HTML_CT,
        sentinel_match=True,
        expected_status=200,
        expected_content_type=HTML_CT,
        reset_confirmed=True,
    )
    assert diag is not None
    assert diag.code == "CONTRACT_MISMATCH"


def test_unexpected_hit_none_when_miss():
    assert (
        check_unexpected_hit(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            cache_status="MISS",
            response_status=200,
            response_content_type=HTML_CT,
            sentinel_match=True,
            expected_status=200,
            expected_content_type=HTML_CT,
            reset_confirmed=True,
        )
        is None
    )


def test_unexpected_hit_none_when_wrong_representation():
    # A HIT serving the wrong representation is the bleed check's
    # job, not this leg's.
    assert (
        check_unexpected_hit(
            request_index=6,
            experiment_id="HTML_TO_MARKDOWN",
            requested_representation="markdown",
            cache_status="HIT",
            response_status=200,
            response_content_type=HTML_CT,
            sentinel_match=False,
            expected_status=200,
            expected_content_type=MD_CT,
            reset_confirmed=True,
        )
        is None
    )


def test_unexpected_hit_none_when_reset_unconfirmed():
    assert (
        check_unexpected_hit(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            cache_status="HIT",
            response_status=200,
            response_content_type=HTML_CT,
            sentinel_match=True,
            expected_status=200,
            expected_content_type=HTML_CT,
            reset_confirmed=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.4 reset leg
# ---------------------------------------------------------------------------


def test_reset_unknown_when_no_reset_recorded():
    diag = check_reset_evidence([])
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"
    assert diag.evidence["cache_reset_confirmed"] is False


def test_reset_unknown_when_reset_failed():
    failed = ResetEvidence(
        namespace="t006-html-cold",
        success=False,
        entries_before=2,
        entries_after=2,
        entries_removed=0,
    )
    diag = check_reset_evidence([reset_ok(), failed])
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_reset_unknown_when_entries_left_behind():
    left = ResetEvidence(
        namespace="t006-html-cold",
        success=True,
        entries_before=1,
        entries_after=1,
        entries_removed=0,
    )
    diag = check_reset_evidence([left])
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_reset_no_diagnostic_when_all_resets_confirmed():
    assert check_reset_evidence([reset_ok(), reset_ok("t006-md-cold")]) is None


def test_reset_no_diagnostic_when_not_supplied():
    assert check_reset_evidence(None) is None


# ---------------------------------------------------------------------------
# Deterministic ordering (§6.3, I-08)
# ---------------------------------------------------------------------------


def test_sort_orders_by_request_not_severity():
    # A WARNING at request 3 must sort before a CRITICAL at request 6:
    # §6.3 forbids re-ordering requests by diagnostic severity.
    late_critical = make_diagnostic(
        "REPRESENTATION_BLEED", "bleed", request_index=6
    )
    early_warning = make_diagnostic(
        "CACHE_STATE_UNKNOWN", "unknown", request_index=3
    )
    assert sort_diagnostics([late_critical, early_warning]) == (
        early_warning,
        late_critical,
    )


def test_sort_tie_break_is_spec_code_order():
    first = make_diagnostic("SENTINEL_MISMATCH", "s", request_index=3)
    second = make_diagnostic("CONTRACT_MISMATCH", "c", request_index=3)
    # §8 order: CONTRACT_MISMATCH (8.3) before SENTINEL_MISMATCH (8.5).
    assert sort_diagnostics([first, second]) == (second, first)


def test_sort_run_level_diagnostics_last():
    run_level = make_diagnostic("CACHE_STATE_UNKNOWN", "reset failed")
    bound = make_diagnostic(
        "CACHE_STATE_UNKNOWN", "unknown", request_index=3
    )
    assert sort_diagnostics([run_level, bound]) == (bound, run_level)


def test_sort_is_stable_for_equal_keys():
    a = make_diagnostic("CACHE_STATE_UNKNOWN", "same", request_index=3)
    b = make_diagnostic("CACHE_STATE_UNKNOWN", "same", request_index=3)
    assert sort_diagnostics([a, b]) == (a, b)
    assert sort_diagnostics([b, a]) == (b, a)


def test_diagnostic_order_rejects_unknown_code():
    with pytest.raises(ValueError, match="unknown diagnostic code"):
        diagnostic_order("NOPE")
```

## tests/unit/test_evidence.py

- SHA-256：`7f08ab185180aecbd5e7ac9adb3a52aaa3cf6e151505044b7bae0b605b953905`
- 字节数：2159

```
"""Unit tests for the evidence-file writer guard (P032 T005).

:func:`accepttwin.evidence.write_evidence_file` must refuse, at any
depth of the evidence dict, any ``body_text`` / ``response_body`` /
``body`` field carrying raw response bytes (§7.12 I-12). Body hashes
(``body_sha256``) and sizes (``body_size``) are allowed.
"""

from __future__ import annotations

import pytest

from accepttwin.evidence import RAW_OBSERVATIONS_FORMAT, write_evidence_file


def _base_evidence():
    return {"format": RAW_OBSERVATIONS_FORMAT, "observations": []}


def test_write_evidence_file_rejects_top_level_body_text(tmp_path):
    evidence = _base_evidence()
    evidence["body_text"] = "<!DOCTYPE html>"
    with pytest.raises(ValueError, match="body_text"):
        write_evidence_file(tmp_path / "out.json", evidence)
    assert not (tmp_path / "out.json").exists()


def test_write_evidence_file_rejects_nested_body_text_in_observation(tmp_path):
    evidence = _base_evidence()
    evidence["observations"] = [
        {
            "request_index": 3,
            "body_sha256": "a" * 64,
            "body_text": "<!DOCTYPE html>",
        }
    ]
    with pytest.raises(ValueError, match="body_text"):
        write_evidence_file(tmp_path / "out.json", evidence)
    assert not (tmp_path / "out.json").exists()


def test_write_evidence_file_rejects_deeply_nested_body_field(tmp_path):
    evidence = _base_evidence()
    evidence["observations"] = [
        {"request_index": 3, "response": {"body": "# markdown"}}
    ]
    with pytest.raises(ValueError, match="'body'"):
        write_evidence_file(tmp_path / "out.json", evidence)
    assert not (tmp_path / "out.json").exists()


def test_write_evidence_file_accepts_hashes_and_sizes(tmp_path):
    evidence = _base_evidence()
    evidence["observations"] = [
        {
            "request_index": 3,
            "body_sha256": "a" * 64,
            "body_size": 128,
            "response_headers": {"x-accepttwin-cache-status": "MISS"},
        }
    ]
    out = write_evidence_file(tmp_path / "out.json", evidence)
    assert out.exists()
    assert "body_sha256" in out.read_text(encoding="utf-8")
```

## tests/unit/test_port_check.py

- SHA-256：`c1051070742bef7e17b030fa47fdb087ce6e96c2c8c75c5ca6f7d43866a4dc8c`
- 字节数：1031

```
"""Direct unit tests for the runner's port check (P032 T005, step 05).

:func:`accepttwin.experiment_runner._check_port_listening` is the
live check behind step 05 (VerifyLocalPorts); these tests exercise
it directly with a real listening socket, no stubs.
"""

from __future__ import annotations

import socket

from accepttwin.experiment_runner import _check_port_listening


def test_check_port_listening_true_for_listening_socket():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        port = server.getsockname()[1]
        assert _check_port_listening("127.0.0.1", port) is True
    finally:
        server.close()


def test_check_port_listening_false_for_dead_port():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    assert _check_port_listening("127.0.0.1", port) is False
```

## tests/unit/test_report_builder.py

- SHA-256：`e3c345a951c677929621b25b592f7e84649964b33a407528b16bad2f7eacbf36`
- 字节数：24375

```
"""Unit tests for the formal report builder (P032 T009, §14, §10.4).

Covers the T009 acceptance criteria that belong to the generator:

* report shape (``accepttwin.report/v1``, five frozen verdicts,
  diagnostic severities, counts, first-error passthrough);
* report hash: recomputed independently in-test, repeat-identical,
  and unchanged when only the port changes (ADR-003) or when only
  hash-excluded evidence changes (cache keys, entry ids, absolute
  counters, port-bearing URLs);
* no raw body text and no sensitive header may enter a report, at
  any depth — forbidden content raises instead of being recorded;
* non-loopback ``redirect_target`` is desensitised (§8.6), loopback
  targets are kept;
* Oracle parity (§12.4, §4.2 constraint 6): matching Oracle makes
  the report final; a mismatch or a missing Oracle never does;
* ``canonical_json`` is a thin re-export of the single
  implementation in ``accepttwin.contract`` — no second
  canonicalisation exists;
* the T012 verify entry point (``scripts/run_all_48.run_all``) is
  importable — the CLI itself belongs to T012, not T009.

Schema conformance of the built reports is *not* asserted here:
that is the job of ``tests/unit/test_report_schema.py``, which
validates with the independent checker that shares no code with
this generator.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from accepttwin.canonical_json import (  # noqa: E402
    canonical_contract_hash,
    canonical_json_bytes,
)
from accepttwin.classifier import ClassificationResult  # noqa: E402
from accepttwin.contract import (  # noqa: E402
    canonical_json_bytes as contract_canonical_json_bytes,
)
from accepttwin.contract import load_contract, parse_contract  # noqa: E402
from accepttwin.diagnostics import make_diagnostic  # noqa: E402
from accepttwin.evidence import RequestObservation  # noqa: E402
from accepttwin.report_builder import (  # noqa: E402
    REDACTED_REDIRECT_TARGET,
    REPORT_HASH_EXCLUDED_FIELDS,
    ReportError,
    build_report,
    compute_report_hash,
    report_hash_payload,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

_HASH = "ab" * 32
_KEY = "cd" * 32
_ENTRY = "entry-" + "cd" * 8

_FORBIDDEN_KEYS = {
    "body",
    "body_text",
    "response_body",
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
}


def _contract(ports=(18765, 18766)):
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = f"http://127.0.0.1:{ports[0]}/doc"
    data["origin_url"] = f"http://127.0.0.1:{ports[1]}/doc"
    return parse_contract(data)


def _observations(cache_key=_KEY, entry=_ENTRY):
    """Eight §5.5 observations for a healthy C01-shaped run."""
    experiments = [
        ("ORIGIN_HTML", "html", None, 1),
        ("ORIGIN_MARKDOWN", "markdown", None, 1),
        ("HTML_COLD", "html", "MISS", 1),
        ("MARKDOWN_COLD", "markdown", "MISS", 1),
        ("HTML_TO_MARKDOWN", "html", "MISS", 1),
        ("HTML_TO_MARKDOWN", "markdown", "MISS", 1),
        ("MARKDOWN_TO_HTML", "markdown", "MISS", 1),
        ("MARKDOWN_TO_HTML", "html", "MISS", 1),
    ]
    counter = 0
    observations = []
    for index, (experiment_id, rep, cache_status, delta) in enumerate(
        experiments, start=1
    ):
        before = counter
        counter += delta
        content_type = (
            "text/html; charset=utf-8"
            if rep == "html"
            else "text/markdown; charset=utf-8"
        )
        observations.append(
            RequestObservation(
                request_index=index,
                experiment_id=experiment_id,
                requested_representation=rep,
                response_status=200,
                response_content_type=content_type,
                body_sha256=_HASH,
                sentinel_match=True,
                cache_status=cache_status,
                cache_key_sha256=(cache_key if cache_status else None),
                cache_entry_id=(entry if cache_status else None),
                origin_counter_before=before,
                origin_counter_after=counter,
                origin_counter_delta=delta,
            )
        )
    return observations


def _pass_result():
    return ClassificationResult(
        verdict="PASS_OBSERVED",
        diagnostics=(),
        first_error=None,
        first_error_experiment_id=None,
        reasons=(
            "baselines, cold requests and both warm orders are correct "
            "with complete cache evidence and no CRITICAL diagnostic",
        ),
        # T014 (T013-F02): classifier-confirmed states matching
        # _observations() — baselines None (ADR-001), proxied MISS.
        confirmed_cache_states=tuple(_matching_cache_states()),
    )


def _matching_cache_states():
    """Per-request verified states for _observations(): baselines
    carry None (ADR-001), the six proxied requests are MISS (T014,
    T013-F02 — the parity check now compares these)."""
    return [
        {"request_index": 1, "state": None},
        {"request_index": 2, "state": None},
        *[
            {"request_index": index, "state": "MISS"}
            for index in range(3, 9)
        ],
    ]


def _matching_oracle():
    return {
        "verdict": "PASS_OBSERVED",
        "diagnostics": [],
        "first_error": None,
        "first_error_experiment_id": None,
        "reasons": ["oracle agrees"],
        "verified_cache_states": _matching_cache_states(),
    }


def _forbidden_keys_anywhere(value, found=None):
    found = found if found is not None else []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                found.append(key)
            _forbidden_keys_anywhere(item, found)
    elif isinstance(value, list):
        for item in value:
            _forbidden_keys_anywhere(item, found)
    return found


def _independent_hash(report):
    """Recompute the report hash without the production helper.

    Same rule as the builder documents (strip the excluded fields,
    drop ``report_hash`` itself), but written out here so the test
    does not just call the code under test and agree with itself.
    """
    def strip(value):
        if isinstance(value, dict):
            return {
                k: strip(v)
                for k, v in value.items()
                if k not in REPORT_HASH_EXCLUDED_FIELDS
            }
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    payload = {
        k: v for k, v in report.items() if k != "report_hash"
    }
    return hashlib.sha256(
        canonical_json_bytes(strip(payload))
    ).hexdigest()


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


def test_report_shape_and_counts():
    report = build_report(
        _contract(),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["schema"] == "accepttwin.report/v1"
    assert report["project"] == {"project_id": "P032", "version": "1.0.1"}
    assert report["scenario_id"] == "C01"
    assert report["verdict"] == "PASS_OBSERVED"
    assert report["first_error"] is None
    assert report["critical_count"] == 0
    assert report["warning_count"] == 0
    assert report["oracle_parity"] is True
    assert report["final"] is True
    assert report["oracle"]["verdict"] == "PASS_OBSERVED"
    assert len(report["observations"]) == 8
    assert [o["request_index"] for o in report["observations"]] == list(range(1, 9))
    assert report["input"]["contract_sha256"] == canonical_contract_hash(
        _contract()
    )
    assert report["input"]["url"] == "http://127.0.0.1:18765/doc"
    assert report["input"]["request_headers"] == {
        "accept_encoding": "identity",
        "user_agent": "AcceptTwin/1.0.0",
        "accept_language": "en",
    }


def test_bleed_report_carries_diagnostics_and_counts():
    diag = make_diagnostic(
        "REPRESENTATION_BLEED",
        "warm-cache request 006 for markdown was served html",
        experiment_id="HTML_TO_MARKDOWN",
        request_index=6,
        evidence={
            "cache_status": "HIT",
            "cache_key_sha256": _KEY,
            "cache_entry_id": _ENTRY,
            "origin_counter_before": 5,
            "origin_counter_after": 5,
            "origin_counter_delta": 0,
            "body_sha256": _HASH,
        },
    )
    result = ClassificationResult(
        verdict="REPRESENTATION_BLEED",
        diagnostics=(diag,),
        first_error=6,
        first_error_experiment_id="HTML_TO_MARKDOWN",
        reasons=["a warm-cache second request was served the other representation"],
        confirmed_cache_states=tuple(_matching_cache_states()),
    )
    oracle = {
        "verdict": "REPRESENTATION_BLEED",
        "diagnostics": [diag.as_dict()],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "verified_cache_states": _matching_cache_states(),
    }
    report = build_report(
        _contract(),
        result,
        oracle,
        observations=_observations(),
        scenario_id="C11",
    )
    assert report["verdict"] == "REPRESENTATION_BLEED"
    assert report["first_error"] == 6
    assert report["first_error_experiment_id"] == "HTML_TO_MARKDOWN"
    assert report["critical_count"] == 1
    assert report["diagnostics"][0]["code"] == "REPRESENTATION_BLEED"
    assert report["oracle_parity"] is True
    assert report["final"] is True


# ---------------------------------------------------------------------------
# Hash: independent recomputation, determinism, port invariance
# ---------------------------------------------------------------------------


def test_report_hash_matches_independent_recomputation():
    report = build_report(
        _contract(),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["report_hash"] == _independent_hash(report)
    assert report["report_hash"] == compute_report_hash(report)


def test_repeat_build_is_identical():
    kwargs = dict(
        observations=_observations(),
        scenario_id="C01",
    )
    first = build_report(_contract(), _pass_result(), _matching_oracle(), **kwargs)
    second = build_report(_contract(), _pass_result(), _matching_oracle(), **kwargs)
    assert first == second
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_port_change_does_not_change_hash():
    """ADR-003: only the OS-assigned ports change — same report hash."""
    base = build_report(
        _contract(ports=(18765, 18766)),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    moved = build_report(
        _contract(ports=(39991, 39992)),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert moved["input"]["url"] == "http://127.0.0.1:39991/doc"
    assert moved["report_hash"] == base["report_hash"]
    # …but a semantic change still changes it.
    other_data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    other_data["contract_id"] = "site-example-002"
    changed = build_report(
        parse_contract(other_data),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert changed["report_hash"] != base["report_hash"]


def test_hash_excludes_port_derived_and_absolute_evidence():
    """Cache keys, entry ids, absolute counters and port-bearing
    URLs are report evidence, never hash input (§10.4, ADR-003)."""
    diag = make_diagnostic(
        "REPRESENTATION_BLEED",
        "warm-cache request 006 for markdown was served html",
        experiment_id="HTML_TO_MARKDOWN",
        request_index=6,
        evidence={
            "cache_status": "HIT",
            "cache_key_sha256": _KEY,
            "cache_entry_id": _ENTRY,
            "origin_counter_before": 5,
            "origin_counter_after": 5,
            "origin_counter_delta": 0,
            "body_sha256": _HASH,
            "request_url": "http://127.0.0.1:11111/doc",
            "redirect_target": "http://127.0.0.1:22222/doc",
        },
    )
    result = ClassificationResult(
        verdict="REPRESENTATION_BLEED",
        diagnostics=(diag,),
        first_error=6,
        first_error_experiment_id="HTML_TO_MARKDOWN",
        reasons=["bleed"],
        confirmed_cache_states=tuple(_matching_cache_states()),
    )
    oracle = {
        "verdict": "REPRESENTATION_BLEED",
        "diagnostics": [diag.as_dict()],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "verified_cache_states": _matching_cache_states(),
    }
    base = build_report(
        _contract(), result, oracle, observations=_observations(), scenario_id="C11"
    )
    other_key = "ee" * 32
    other_diag = make_diagnostic(
        "REPRESENTATION_BLEED",
        "warm-cache request 006 for markdown was served html",
        experiment_id="HTML_TO_MARKDOWN",
        request_index=6,
        evidence={
            "cache_status": "HIT",
            "cache_key_sha256": other_key,
            "cache_entry_id": "entry-" + "ee" * 8,
            "origin_counter_before": 500,
            "origin_counter_after": 500,
            "origin_counter_delta": 0,
            "body_sha256": _HASH,
            "request_url": "http://127.0.0.1:33333/doc",
            "redirect_target": "http://127.0.0.1:44444/doc",
        },
    )
    other_result = ClassificationResult(
        verdict="REPRESENTATION_BLEED",
        diagnostics=(other_diag,),
        first_error=6,
        first_error_experiment_id="HTML_TO_MARKDOWN",
        reasons=["bleed"],
        confirmed_cache_states=tuple(_matching_cache_states()),
    )
    other_oracle = {
        "verdict": "REPRESENTATION_BLEED",
        "diagnostics": [other_diag.as_dict()],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "verified_cache_states": _matching_cache_states(),
    }
    changed = build_report(
        _contract(),
        other_result,
        other_oracle,
        observations=_observations(cache_key=other_key),
        scenario_id="C11",
    )
    assert changed["report_hash"] == base["report_hash"]
    # The evidence itself is still in the report, just not hashed.
    assert changed["diagnostics"][0]["evidence"]["cache_key_sha256"] == other_key
    assert changed["diagnostics"][0]["evidence"]["origin_counter_before"] == 500
    assert report_hash_payload(changed)["diagnostics"][0]["evidence"] == {
        "cache_status": "HIT",
        "origin_counter_delta": 0,
        "body_sha256": _HASH,
    }


# ---------------------------------------------------------------------------
# Privacy: no body text, no sensitive headers, desensitised redirects
# ---------------------------------------------------------------------------


def test_no_forbidden_keys_anywhere_in_report():
    report = build_report(
        _contract(),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert _forbidden_keys_anywhere(report) == []


def _dict_diagnostic(code, severity, evidence):
    return {
        "code": code,
        "severity": severity,
        "message": "synthetic diagnostic",
        "experiment_id": "HTML_TO_MARKDOWN",
        "request_index": 6,
        "evidence": evidence,
    }


@pytest.mark.parametrize("key", sorted(_FORBIDDEN_KEYS))
def test_forbidden_evidence_key_is_rejected(key):
    production = {
        "verdict": "CONTRACT_MISMATCH",
        "diagnostics": [
            _dict_diagnostic(
                "CONTRACT_MISMATCH", "CRITICAL", {key: "secret-value"}
            )
        ],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "reasons": ["contract error"],
    }
    with pytest.raises(ReportError):
        build_report(
            _contract(),
            production,
            None,
            observations=_observations(),
            scenario_id="C11",
        )


def test_redirect_target_desensitisation():
    production = {
        "verdict": "INCONCLUSIVE",
        "diagnostics": [
            _dict_diagnostic(
                "INCONCLUSIVE_LIMIT",
                "WARNING",
                {
                    "limit_code": "redirect",
                    "redirect_target": "http://example.com/doc",
                    "request_url": "http://127.0.0.1:38977/doc",
                    "response_status": 301,
                },
            ),
            _dict_diagnostic(
                "INCONCLUSIVE_LIMIT",
                "WARNING",
                {
                    "limit_code": "redirect",
                    "redirect_target": "http://127.0.0.1:36321/doc",
                    "request_url": "http://127.0.0.1:38977/doc",
                    "response_status": 301,
                },
            ),
        ],
        "first_error": 3,
        "first_error_experiment_id": "HTML_COLD",
        "reasons": ["redirect"],
    }
    report = build_report(
        _contract(),
        production,
        None,
        observations=_observations(),
        scenario_id="E22",
    )
    targets = [
        d["evidence"]["redirect_target"] for d in report["diagnostics"]
    ]
    assert targets[0] == REDACTED_REDIRECT_TARGET
    assert targets[1] == "http://127.0.0.1:36321/doc"


# ---------------------------------------------------------------------------
# Oracle parity / final marking (§4.2 constraint 6)
# ---------------------------------------------------------------------------


def test_oracle_mismatch_is_never_final():
    oracle = _matching_oracle()
    oracle["verdict"] = "CONTRACT_MISMATCH"
    report = build_report(
        _contract(),
        _pass_result(),
        oracle,
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["oracle_parity"] is False
    assert report["final"] is False


def test_missing_oracle_is_never_final():
    report = build_report(
        _contract(),
        _pass_result(),
        None,
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["oracle"] is None
    assert report["oracle_parity"] is None
    assert report["final"] is False


def test_cache_state_disagreement_fails_parity_t014():
    """T014 (T013-F02): verdict, diagnostics and first error all
    agree, but one per-request verified cache state differs — the
    old parity check passed this silently; the widened check must
    fail it."""
    oracle = _matching_oracle()
    states = _matching_cache_states()
    states[2] = {"request_index": 3, "state": "HIT"}  # production says MISS
    oracle["verified_cache_states"] = states
    report = build_report(
        _contract(),
        _pass_result(),
        oracle,
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["oracle_parity"] is False
    assert report["final"] is False


def test_oracle_without_cache_states_fails_parity_t014():
    """T014 (T013-F02): an Oracle result without per-request cache
    states fails parity (fail-closed), even when everything else
    agrees."""
    oracle = _matching_oracle()
    del oracle["verified_cache_states"]
    report = build_report(
        _contract(),
        _pass_result(),
        oracle,
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["oracle_parity"] is False
    assert report["final"] is False


# ---------------------------------------------------------------------------
# Fail-closed inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda obs: obs[:7],
        lambda obs: obs + [obs[0]],
        lambda obs: [dict(o, request_index=9) if o["request_index"] == 8 else o for o in obs],
    ],
)
def test_observation_count_and_coverage_are_enforced(mutate):
    observations = mutate(
        [o.as_dict() for o in _observations()]
    )
    with pytest.raises(ReportError):
        build_report(
            _contract(),
            _pass_result(),
            None,
            observations=observations,
            scenario_id="C01",
        )


def test_invalid_verdict_and_diagnostic_are_rejected():
    bad_verdict = {
        "verdict": "MAYBE",
        "diagnostics": [],
        "first_error": None,
        "first_error_experiment_id": None,
        "reasons": [],
    }
    with pytest.raises(ReportError):
        build_report(
            _contract(), bad_verdict, None,
            observations=_observations(), scenario_id="C01",
        )
    bad_diag = {
        "verdict": "CONTRACT_MISMATCH",
        "diagnostics": [
            _dict_diagnostic("NOT_A_CODE", "CRITICAL", {})
        ],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "reasons": [],
    }
    with pytest.raises(ReportError):
        build_report(
            _contract(), bad_diag, None,
            observations=_observations(), scenario_id="C01",
        )
    wrong_severity = {
        "verdict": "CONTRACT_MISMATCH",
        "diagnostics": [
            _dict_diagnostic("CONTRACT_MISMATCH", "WARNING", {})
        ],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "reasons": [],
    }
    with pytest.raises(ReportError):
        build_report(
            _contract(), wrong_severity, None,
            observations=_observations(), scenario_id="C01",
        )


def test_missing_scenario_id_and_observations_are_rejected():
    with pytest.raises(ReportError):
        build_report(
            _contract(), _pass_result(), None,
            observations=_observations(), scenario_id=None,
        )
    with pytest.raises(ReportError):
        build_report(
            _contract(), _pass_result(), None,
            observations=None, scenario_id="C01",
        )


# ---------------------------------------------------------------------------
# Canonical JSON: single source, thin re-export only
# ---------------------------------------------------------------------------


def test_canonical_json_is_thin_reexport_of_contract():
    import accepttwin.canonical_json as cj

    assert cj.canonical_json_bytes is contract_canonical_json_bytes
    assert cj.canonical_contract_hash is canonical_contract_hash
    source = Path(cj.__file__).read_text(encoding="utf-8")
    assert "def canonical_json_bytes" not in source
    assert "def canonical_contract_hash" not in source
    assert "sort_keys" not in source
    assert "json.dumps" not in source
    assert "single source" in source.lower() or "Single source" in source


# ---------------------------------------------------------------------------
# T012 handoff: the verify entry point is importable (CLI is T012's)
# ---------------------------------------------------------------------------


def test_verify_entry_point_importable_for_t012():
    """``scripts/run_all_48.run_all`` is the importable verify
    function T012's ``verify --suite all`` CLI calls. The CLI entry
    itself (``__main__.py`` / ``cli.py``) belongs to T012: §4.2
    assigns no CLI file to T009, and T012's acceptance requires
    both ``verify`` and ``benchmark`` in one CLI file, so one task
    must own the file — T012. T008 P2-1 therefore stays open after
    T009 and is closed by T012, which flips this test from
    "CLI must not exist yet" to "CLI exists and delegates".
    """
    from run_all_48 import run_all

    assert callable(run_all)
    assert (ROOT / "src" / "accepttwin" / "__main__.py").is_file()
    assert (ROOT / "src" / "accepttwin" / "cli.py").is_file()
    from accepttwin.cli import cmd_benchmark, cmd_verify, main

    assert callable(main) and callable(cmd_verify) and callable(cmd_benchmark)
```

## tests/unit/test_report_schema.py

- SHA-256：`e9a9ce310abab03089bf85dda5e7038705f7b66ae263a09dc4c65ce073c346e6`
- 字节数：24694

```
"""Tests for the formal report Schema (P032 T009, §14.3).

Every assertion here runs through
``tests/unit/independent_schema_validator.py`` — a minimal
validator that reads only the Schema file and never imports
``accepttwin.report_builder`` (or any production module). The
production generator is therefore never trusted to validate
itself; a report passes here only because an independent checker
says so.

Coverage:

* Schema meta: Draft 2020-12, top-level ``additionalProperties:
  false``, and the Schema stays inside the keyword subset the
  independent validator implements (so the checker cannot silently
  weaken);
* a hand-written minimal valid report (built literally, with no
  production code) validates — proving the validator, not just
  the generator;
* one mutation per acceptance rule is rejected: extra top-level
  field, verdict outside the five frozen values, severity outside
  CRITICAL/WARNING, non-positive ``request_index``, non-integer
  ``origin_counter_delta``, malformed hashes, non-loopback URLs,
  sensitive fields (``Authorization`` / ``Cookie``) at top level
  and inside diagnostic evidence, body-text fields, wrong cache
  status, wrong observation count, missing required field;
* all 48 committed samples in ``evidence/Reports/`` validate,
  match the recorded Golden verdicts, carry no forbidden key and
  no non-loopback URL, and their hashes recompute independently;
* committed samples equal what the generator builds from the
  recorded evidence (reproducibility, checked for C01/C11/E22).
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from independent_schema_validator import (  # noqa: E402
    SUPPORTED_KEYWORDS,
    load_schema,
    validate,
    validate_report_file,
)
from accepttwin.contract import canonical_json_bytes  # noqa: E402
from accepttwin.report_builder import (  # noqa: E402
    REPORT_HASH_EXCLUDED_FIELDS,
    build_report,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "accepttwin.report.v1.schema.json"
REPORTS_DIR = ROOT / "evidence" / "Reports"
GOLDEN_DIR = ROOT / "evidence" / "Golden"

SCENARIO_IDS = tuple(
    [f"C{i:02d}" for i in range(1, 25)] + [f"E{i:02d}" for i in range(1, 25)]
)

_HASH = "ab" * 32
_KEY = "cd" * 32

_FORBIDDEN_KEYS = {
    "body",
    "body_text",
    "response_body",
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
}


def _minimal_valid_report():
    """A valid report written literally — no production code."""
    observations = []
    for index, (experiment_id, rep) in enumerate(
        [
            ("ORIGIN_HTML", "html"),
            ("ORIGIN_MARKDOWN", "markdown"),
            ("HTML_COLD", "html"),
            ("MARKDOWN_COLD", "markdown"),
            ("HTML_TO_MARKDOWN", "html"),
            ("HTML_TO_MARKDOWN", "markdown"),
            ("MARKDOWN_TO_HTML", "markdown"),
            ("MARKDOWN_TO_HTML", "html"),
        ],
        start=1,
    ):
        content_type = (
            "text/html; charset=utf-8"
            if rep == "html"
            else "text/markdown; charset=utf-8"
        )
        observations.append(
            {
                "request_index": index,
                "experiment_id": experiment_id,
                "requested_representation": rep,
                "response_status": 200,
                "response_content_type": content_type,
                "body_sha256": _HASH,
                "sentinel_match": True,
                "cache_status": "MISS" if index > 2 else None,
                "cache_key_sha256": _KEY if index > 2 else None,
                "cache_entry_id": "entry-" + "cd" * 8 if index > 2 else None,
                "origin_counter_delta": 1,
            }
        )
    return {
        "schema": "accepttwin.report/v1",
        "project": {"project_id": "P032", "version": "1.0.1"},
        "scenario_id": "C01",
        "input": {
            "contract_id": "s0-C01",
            "contract_sha256": _HASH,
            "url": "http://127.0.0.1:18765/doc",
            "origin_url": "http://127.0.0.1:18766/doc",
            "cache_behavior": {
                "mode": "variant_by_accept",
                "vary_accept": "advisory",
                "max_age_seconds": 60,
            },
            "request_headers": {
                "accept_encoding": "identity",
                "user_agent": "AcceptTwin/1.0.0",
                "accept_language": "en",
            },
        },
        "observations": observations,
        "diagnostics": [],
        "verdict": "PASS_OBSERVED",
        "first_error": None,
        "first_error_experiment_id": None,
        "critical_count": 0,
        "warning_count": 0,
        "reasons": ["all checks passed"],
        "oracle": {
            "verdict": "PASS_OBSERVED",
            "first_error": None,
            "first_error_experiment_id": None,
        },
        "oracle_parity": True,
        "final": True,
        "report_hash": _HASH,
    }


def _forbidden_keys_anywhere(value, found=None):
    found = found if found is not None else []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                found.append(key)
            _forbidden_keys_anywhere(item, found)
    elif isinstance(value, list):
        for item in value:
            _forbidden_keys_anywhere(item, found)
    return found


def _independent_hash(report):
    """Recompute the report hash without the production helper."""
    def strip(value):
        if isinstance(value, dict):
            return {
                k: strip(v)
                for k, v in value.items()
                if k not in REPORT_HASH_EXCLUDED_FIELDS
            }
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    payload = {k: v for k, v in report.items() if k != "report_hash"}
    return hashlib.sha256(canonical_json_bytes(strip(payload))).hexdigest()


def _schema_keywords(schema, found=None):
    """Collect the keyword names used by *schema*.

    Property names (keys of ``properties``) and definition names
    (keys of ``$defs``) are field names, not keywords, and are
    skipped; every other dict key of a schema object is a keyword.
    """
    found = found if found is not None else set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in ("properties", "$defs"):
                for sub in value.values():
                    _schema_keywords(sub, found)
            else:
                found.add(key)
                _schema_keywords(value, found)
    elif isinstance(schema, list):
        for item in schema:
            _schema_keywords(item, found)
    return found


# ---------------------------------------------------------------------------
# Schema meta
# ---------------------------------------------------------------------------


def test_schema_is_draft_2020_12_with_closed_top_level():
    schema = load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema"]["const"] == "accepttwin.report/v1"
    for field in (
        "schema",
        "project",
        "scenario_id",
        "input",
        "observations",
        "diagnostics",
        "verdict",
        "first_error",
        "first_error_experiment_id",
        "critical_count",
        "warning_count",
        "reasons",
        "oracle",
        "oracle_parity",
        "final",
        "report_hash",
    ):
        assert field in schema["required"]


def test_schema_stays_inside_validator_subset():
    schema = load_schema()
    used = _schema_keywords(schema)
    unsupported = used - SUPPORTED_KEYWORDS - {
        "$schema",
        "$id",
        "title",
        "description",
    }
    assert unsupported == set(), f"unsupported keywords in schema: {unsupported}"


def test_hand_written_minimal_report_validates():
    assert validate(_minimal_valid_report()) == []


# ---------------------------------------------------------------------------
# One rejected mutation per acceptance rule
# ---------------------------------------------------------------------------


def _mutated(mutate):
    report = _minimal_valid_report()
    mutate(report)
    return report


@pytest.mark.parametrize(
    "name,mutate",
    [
        (
            "extra top-level field",
            lambda r: r.update({"body_text": "hello"}),
        ),
        (
            "extra top-level sensitive field",
            lambda r: r.update({"authorization": "Bearer x"}),
        ),
        ("verdict outside enum", lambda r: r.update({"verdict": "MAYBE"})),
        (
            "severity outside enum",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "INFO",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {},
                }
            ),
        ),
        (
            "unknown diagnostic code",
            lambda r: r["diagnostics"].append(
                {
                    "code": "NOT_A_CODE",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {},
                }
            ),
        ),
        (
            "request_index zero in observation",
            lambda r: r["observations"][0].update({"request_index": 0}),
        ),
        (
            "request_index zero in diagnostic",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 0,
                    "evidence": {},
                }
            ),
        ),
        (
            "origin_counter_delta as string",
            lambda r: r["observations"][0].update(
                {"origin_counter_delta": "1"}
            ),
        ),
        (
            "body_sha256 uppercase",
            lambda r: r["observations"][0].update(
                {"body_sha256": "AB" * 32}
            ),
        ),
        (
            "body_sha256 short",
            lambda r: r["observations"][0].update({"body_sha256": "abcd"}),
        ),
        (
            "contract_sha256 short",
            lambda r: r["input"].update({"contract_sha256": "abcd"}),
        ),
        (
            "report_hash wrong format",
            lambda r: r.update({"report_hash": "not-a-hash"}),
        ),
        (
            "non-loopback url",
            lambda r: r["input"].update({"url": "http://example.com/doc"}),
        ),
        (
            "non-loopback origin_url",
            lambda r: r["input"].update(
                {"origin_url": "http://192.168.1.10/doc"}
            ),
        ),
        (
            "https url",
            lambda r: r["input"].update(
                {"url": "https://127.0.0.1:18765/doc"}
            ),
        ),
        # T009-FIX (P2-1): the loopback URL pattern now checks octet
        # range (0-255) and port range (1-65535), not just digit count.
        (
            "url 127.999.0.1 octet out of range",
            lambda r: r["input"].update(
                {"url": "http://127.999.0.1:18765/doc"}
            ),
        ),
        (
            "url 127.0.0.256 octet out of range",
            lambda r: r["input"].update(
                {"url": "http://127.0.0.256/doc"}
            ),
        ),
        (
            "origin_url 127.999.0.1 octet out of range",
            lambda r: r["input"].update(
                {"origin_url": "http://127.999.0.1:18766/doc"}
            ),
        ),
        (
            "url port 0",
            lambda r: r["input"].update(
                {"url": "http://127.0.0.1:0/doc"}
            ),
        ),
        (
            "url port 65536",
            lambda r: r["input"].update(
                {"url": "http://127.0.0.1:65536/doc"}
            ),
        ),
        (
            "url port 99999",
            lambda r: r["input"].update(
                {"url": "http://127.0.0.1:99999/doc"}
            ),
        ),
        (
            "cookie inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"cookie": "session=1"},
                }
            ),
        ),
        (
            "authorization inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"Authorization": "Bearer x"},
                }
            ),
        ),
        (
            "body_text inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "SENTINEL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"body_text": "<html>…"},
                }
            ),
        ),
        # T009-FIX (P1-1): the evidence propertyNames ban is
        # case-insensitive — every forbidden key must be rejected in
        # ALL-CAPS and mixed case too, not just its original casing.
        (
            "AUTHORIZATION inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"AUTHORIZATION": "Bearer x"},
                }
            ),
        ),
        (
            "COOKIE inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"COOKIE": "session=1"},
                }
            ),
        ),
        (
            "BODY inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "SENTINEL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"BODY": "<html>…"},
                }
            ),
        ),
        (
            "BODY_TEXT inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "SENTINEL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"BODY_TEXT": "<html>…"},
                }
            ),
        ),
        (
            "RESPONSE_BODY inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "SENTINEL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"RESPONSE_BODY": "<html>…"},
                }
            ),
        ),
        (
            "PROXY-AUTHORIZATION inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"PROXY-AUTHORIZATION": "Basic x"},
                }
            ),
        ),
        (
            "SET-COOKIE inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"SET-COOKIE": "session=1"},
                }
            ),
        ),
        (
            "Proxy-Authorization mixed case inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"Proxy-Authorization": "Basic x"},
                }
            ),
        ),
        (
            "Set-Cookie mixed case inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"Set-Cookie": "session=1"},
                }
            ),
        ),
        (
            "AuThOrIzAtIoN mixed case inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"AuThOrIzAtIoN": "Bearer x"},
                }
            ),
        ),
        (
            "cache_status outside enum",
            lambda r: r["observations"][2].update({"cache_status": "MAYBE"}),
        ),
        ("seven observations", lambda r: r["observations"].pop()),
        ("missing verdict", lambda r: r.pop("verdict")),
        ("missing report_hash", lambda r: r.pop("report_hash")),
        ("first_error zero", lambda r: r.update({"first_error": 0})),
        ("scenario_id outside pattern", lambda r: r.update({"scenario_id": "X99"})),
        (
            "unknown request header",
            lambda r: r["input"]["request_headers"].update(
                {"authorization": "Bearer x"}
            ),
        ),
    ],
)
def test_rejected_mutations(name, mutate):
    errors = validate(_mutated(mutate))
    assert errors, f"{name}: expected rejection, got none"


def test_valid_variants_still_pass():
    """Null cache status (baselines), null oracle and non-final
    reports are all schema-valid — the Schema must not over-reject."""
    report = _minimal_valid_report()
    report["oracle"] = None
    report["oracle_parity"] = None
    report["final"] = False
    assert validate(report) == []
    report = _minimal_valid_report()
    report["verdict"] = "INCONCLUSIVE"
    report["diagnostics"] = [
        {
            "code": "CACHE_STATE_UNKNOWN",
            "severity": "WARNING",
            "message": "evidence missing",
            "experiment_id": None,
            "request_index": None,
            "evidence": {"cache_reset_confirmed": False},
        }
    ]
    report["warning_count"] = 1
    assert validate(report) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:18765/doc",
        "http://127.0.0.2:18765/doc",
        "http://127.255.255.255/doc",
        "http://127.0.0.1:65535/doc",
        "http://127.0.0.1:1/doc",
        "http://[::1]:18765/doc",
        "http://[::1]/doc",
        "http://localhost:18765/doc",
        "http://localhost/doc",
    ],
)
def test_valid_loopback_url_variants_still_pass(url):
    """T009-FIX (P2-1): tightening the loopback pattern must not
    over-reject genuine loopback URLs — 127.0.0.1 / 127.0.0.2 /
    [::1] / localhost, at the port boundaries 1 and 65535, all stay
    valid."""
    report = _minimal_valid_report()
    report["input"]["url"] = url
    assert validate(report) == []


# ---------------------------------------------------------------------------
# The 48 committed samples
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", SCENARIO_IDS)
def test_all_48_samples_validate_independently(sid):
    path = REPORTS_DIR / f"{sid}.json"
    assert path.exists(), f"missing report sample {path}"
    errors = validate_report_file(path)
    assert errors == [], f"{sid}: {errors}"
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["report_hash"] == _independent_hash(report)
    assert report["oracle_parity"] is True
    assert report["final"] is True
    recorded = json.loads((GOLDEN_DIR / sid / "scenario.json").read_text(encoding="utf-8"))
    assert report["verdict"] == recorded["verdict"]
    assert report["first_error"] == recorded["first_error"]
    assert _forbidden_keys_anywhere(report) == []


@pytest.mark.parametrize("sid", SCENARIO_IDS)
def test_samples_contain_only_loopback_urls(sid):
    report = json.loads((REPORTS_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    urls: list[str] = []

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)

    walk(report)
    assert urls, f"{sid}: report carries no URL at all"
    for url in urls:
        parsed = urlsplit(url)
        assert parsed.scheme == "http", f"{sid}: non-http URL {url}"
        host = parsed.hostname or ""
        assert host in ("127.0.0.1", "localhost", "::1") or host.startswith(
            "127."
        ), f"{sid}: non-loopback URL {url}"


@pytest.mark.parametrize("sid", ["C01", "C11", "E22"])
def test_committed_samples_match_generator(sid):
    """Rebuilding a sample from the recorded evidence reproduces
    the committed file byte-for-byte in content (dict equality)."""
    sdir = GOLDEN_DIR / sid
    contract = json.loads((sdir / "contract.json").read_text(encoding="utf-8"))
    raw = json.loads((sdir / "raw-observations.json").read_text(encoding="utf-8"))
    production = json.loads((sdir / "production.json").read_text(encoding="utf-8"))
    oracle = json.loads((sdir / "oracle.json").read_text(encoding="utf-8"))
    observations = []
    for record in raw["observations"]:
        observations.append(
            {
                "request_index": record["request_index"],
                "experiment_id": record["experiment_id"],
                "requested_representation": record["requested_representation"],
                "response_status": record["response_status"],
                "response_content_type": record["response_content_type"],
                "body_sha256": record["body_sha256"],
                "sentinel_match": record["sentinel_match"],
                "cache_status": record.get("verified_cache_state"),
                "cache_key_sha256": record.get("cache_key_sha256"),
                "cache_entry_id": record.get("cache_entry_id"),
                "origin_counter_delta": record["origin_counter_delta"],
            }
        )
    rebuilt = build_report(
        contract, production, oracle, observations=observations, scenario_id=sid
    )
    committed = json.loads((REPORTS_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    assert rebuilt == committed
```

## tests/unit/test_request_headers.py

- SHA-256：`3b5853ead435f2e64b1447c5551fae8ad1ad6fd5d6bb3e678360f766ead3c2ca`
- 字节数：4200

```
"""Unit tests for accepttwin.request_headers (T002 acceptance criteria).

Covers: the fixed header set is built exactly; any header outside the
whitelist — Cookie, Authorization, X-*, Cache-Control, Referer, Origin,
or a wrong fixed value — is rejected, never silently dropped.
"""

from __future__ import annotations

import pytest

from accepttwin.request_headers import (
    HeaderError,
    assert_request_headers,
    build_request_headers,
    validate_request_headers,
)


def test_build_html_headers():
    assert build_request_headers("html") == {
        "Accept": "text/html",
        "Accept-Encoding": "identity",
        "User-Agent": "AcceptTwin/1.0.0",
        "Accept-Language": "en",
    }


def test_build_markdown_headers():
    assert build_request_headers("markdown") == {
        "Accept": "text/markdown",
        "Accept-Encoding": "identity",
        "User-Agent": "AcceptTwin/1.0.0",
        "Accept-Language": "en",
    }


def test_build_unknown_representation_rejected():
    with pytest.raises(HeaderError, match="unknown representation"):
        build_request_headers("text")


def test_fixed_sets_validate():
    for representation in ("html", "markdown"):
        assert validate_request_headers(build_request_headers(representation)) == []


def test_lowercase_names_validate():
    headers = {
        "accept": "text/html",
        "accept-encoding": "identity",
        "user-agent": "AcceptTwin/1.0.0",
        "accept-language": "en",
    }
    assert validate_request_headers(headers) == []
    assert assert_request_headers(headers) == build_request_headers("html")


@pytest.mark.parametrize(
    "name",
    [
        "Cookie",
        "cookie",
        "COOKIE",
        "Authorization",
        "Proxy-Authorization",
        "Referer",
        "Origin",
        "Cache-Control",
        "X-Custom",
        "X-AcceptTwin-Debug",
        "X-Forwarded-For",
    ],
)
def test_forbidden_headers_rejected(name):
    headers = build_request_headers("html")
    headers[name] = "x"
    errors = validate_request_headers(headers)
    assert errors, f"{name} should have been rejected"
    with pytest.raises(HeaderError):
        assert_request_headers(headers)


def test_unknown_header_rejected():
    headers = build_request_headers("html")
    headers["DNT"] = "1"
    assert any("not in the fixed" in e for e in validate_request_headers(headers))


@pytest.mark.parametrize("accept", ["text/plain", "text/html;q=0.9", ""])
def test_wrong_accept_rejected(accept):
    headers = build_request_headers("html")
    headers["Accept"] = accept
    assert any("Accept" in e for e in validate_request_headers(headers))


def test_missing_accept_rejected():
    headers = build_request_headers("html")
    del headers["Accept"]
    assert any("missing required header 'Accept'" in e for e in validate_request_headers(headers))


@pytest.mark.parametrize(
    "name,value",
    [
        ("User-Agent", "curl/8.0"),
        ("Accept-Encoding", "gzip"),
        ("Accept-Language", "fr"),
    ],
)
def test_wrong_fixed_value_rejected(name, value):
    headers = build_request_headers("markdown")
    headers[name] = value
    assert validate_request_headers(headers)


def test_missing_fixed_header_rejected():
    headers = build_request_headers("html")
    del headers["User-Agent"]
    assert any("User-Agent" in e for e in validate_request_headers(headers))


def test_case_duplicate_header_rejected():
    headers = {"Accept": "text/html", "accept": "text/html"}
    # A plain dict cannot hold both spellings as separate keys only if the
    # spellings differ; here they do, so the validator must flag it.
    errors = validate_request_headers(headers)
    assert any("differs only by case" in e for e in errors)


def test_non_string_value_rejected():
    errors = validate_request_headers({"Accept": 42})  # type: ignore[dict-item]
    assert errors


def test_assert_returns_canonical_build():
    mixed_case = {
        "accept": "text/markdown",
        "ACCEPT-ENCODING": "identity",
        "user-agent": "AcceptTwin/1.0.0",
        "Accept-Language": "en",
    }
    assert assert_request_headers(mixed_case) == build_request_headers("markdown")
```

## tests/unit/test_url_guard.py

- SHA-256：`c85ccf19a91b71f50269870a04db2bfa4e5fbef7bf2cb77091f34c10080c24be`
- 字节数：4368

```
"""Unit tests for accepttwin.url_guard (T002 acceptance criteria).

Covers: loopback addresses accepted; non-loopback addresses rejected;
non-HTTP schemes rejected; URL userinfo rejected; illegal ports rejected.
"""

from __future__ import annotations

import pytest

from accepttwin.url_guard import URLGuardError, validate_loopback_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:18765/doc",
        "http://127.0.0.1/doc",
        "http://127.0.0.2:8080/",
        "http://[::1]:18766/doc",
        "http://[::1]/doc",
        "http://localhost:18765/doc",
        "http://localhost/doc",
        "HTTP://127.0.0.1:18765/doc",
    ],
)
def test_loopback_urls_accepted(url):
    validated = validate_loopback_url(url)
    assert validated.scheme == "http"
    assert validated.port >= 1
    assert validated.addresses
    assert all(
        addr.startswith("127.") or addr == "::1"
        for addr in validated.addresses
    )


def test_validated_url_fields():
    validated = validate_loopback_url("http://127.0.0.1:18765/doc?x=1")
    assert validated.host == "127.0.0.1"
    assert validated.port == 18765
    assert validated.path == "/doc"
    assert validated.query == "x=1"
    assert validated.addresses == ("127.0.0.1",)
    assert validated.origin == "http://127.0.0.1:18765"


def test_default_port_is_80():
    assert validate_loopback_url("http://127.0.0.1/doc").port == 80


def test_ipv6_validated_url_origin_bracketed():
    validated = validate_loopback_url("http://[::1]:18766/doc")
    assert validated.host == "::1"
    assert validated.origin == "http://[::1]:18766"


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8/doc",
        "http://93.184.216.34:18765/doc",
        "http://192.168.1.1:18765/doc",
        "http://10.0.0.5/doc",
        "http://172.16.0.1/doc",
        "http://0.0.0.0:18765/doc",
        "http://[2606:4700:4700::1111]/doc",
        "http://[2001:db8::1]/doc",
    ],
)
def test_non_loopback_rejected(url):
    with pytest.raises(URLGuardError, match="non-loopback"):
        validate_loopback_url(url)


def test_dns_name_resolving_to_public_rejected():
    # example.com resolves to public IPs (or not at all offline); either
    # way the guard must refuse it — it can never be proven loopback.
    with pytest.raises(URLGuardError):
        validate_loopback_url("http://example.com/doc")


def test_unresolvable_host_rejected():
    # In this VM a wildcard resolver answers even for .invalid names
    # (198.18.179.212); either way the guard must refuse: the name can
    # never be proven loopback.
    with pytest.raises(URLGuardError):
        validate_loopback_url("http://nonexistent.invalid/doc")


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:18765/doc",
        "ftp://127.0.0.1/doc",
        "http://127.0.0.1:18765/doc".replace("http", "ws"),
        "",
    ],
)
def test_non_http_rejected(url):
    with pytest.raises(URLGuardError, match="only 'http'|non-empty"):
        validate_loopback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://user@127.0.0.1:18765/doc",
        "http://user:pass@127.0.0.1:18765/doc",
        "http://:pass@127.0.0.1/doc",
        "http://user@[::1]:18766/doc",
    ],
)
def test_userinfo_rejected(url):
    with pytest.raises(URLGuardError, match="userinfo"):
        validate_loopback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:0/doc",
        "http://127.0.0.1:65536/doc",
        "http://127.0.0.1:99999/doc",
        "http://127.0.0.1:abc/doc",
        "http://127.0.0.1:-1/doc",
    ],
)
def test_illegal_port_rejected(url):
    with pytest.raises(URLGuardError, match="port"):
        validate_loopback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http:///doc",
        "http://:18765/doc",
        "http://127.0.0.1:18765/doc#frag",
        "http://[::1%lo]:18766/doc",
        "http://127.0.0.1:18765/do c",
        "not a url",
    ],
)
def test_malformed_urls_rejected(url):
    with pytest.raises(URLGuardError):
        validate_loopback_url(url)


def test_localhost_resolves_to_loopback_only():
    validated = validate_loopback_url("http://localhost:18765/doc")
    assert validated.addresses
    assert all(
        addr.startswith("127.") or addr == "::1"
        for addr in validated.addresses
    )
```

## tests/unit/test_verify_s0_parity.py

- SHA-256：`0181995cd3c57fc4543803b1ab8b6b6fd0e8937bdb600e9a99f78e5f8661a5b7`
- 字节数：5650

```
"""Unit tests (P032 P2-01 FIX-R1): the widened Oracle parity check in
``scripts/verify_s0.py``.

The runtime parity (``scripts/s0_harness.py`` check_parity) and the
report-builder parity already compare the eight per-request verified
MISS/HIT/BYPASS states; the independent verifier did not. These tests
pin the verifier's widened definition
(:func:`verify_s0.check_oracle_parity`): verdict + diagnostics +
first error + all eight states, with a missing or malformed state
list failing closed instead of counting as agreement.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY_S0 = ROOT / "scripts" / "verify_s0.py"


def _load_verify_s0():
    spec = importlib.util.spec_from_file_location("verify_s0", VERIFY_S0)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("verify_s0", module)
    spec.loader.exec_module(module)
    return module


verify_s0 = _load_verify_s0()


def _load_evidence(sid: str) -> tuple[dict, dict]:
    production = json.loads(
        (ROOT / "evidence" / "S0" / sid / "production.json").read_text(
            encoding="utf-8"
        )
    )
    oracle = json.loads(
        (ROOT / "evidence" / "S0" / sid / "oracle.json").read_text(encoding="utf-8")
    )
    return production, oracle


def test_parity_passes_on_real_c01_evidence():
    production, oracle = _load_evidence("C01")
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert ok, detail


def test_parity_passes_on_real_c11_bleed_evidence():
    production, oracle = _load_evidence("C11")
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert ok, detail
    states = {s["request_index"]: s["state"] for s in oracle["verified_cache_states"]}
    assert states[6] == "HIT" and states[8] == "HIT"


def test_parity_passes_on_real_c21_unconfirmed_evidence():
    # C21: the classifier confirms nothing (CACHE_STATE_UNKNOWN) and
    # the Oracle reports None — the widened check must accept that
    # agreement, not treat "unknown" as a mismatch.
    production, oracle = _load_evidence("C21")
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert ok, detail


def test_parity_fails_on_single_state_mismatch():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verified_cache_states"][5]["state"] = "HIT"
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok
    assert "verified_cache_states" in detail


def test_parity_fails_when_oracle_states_missing():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    del oracle["verified_cache_states"]
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok
    assert "verified_cache_states" in detail


def test_parity_fails_when_oracle_states_short():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verified_cache_states"] = oracle["verified_cache_states"][:7]
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok


def test_parity_fails_on_illegal_state_value():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verified_cache_states"][2]["state"] = "MAYBE"
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok


def test_parity_fails_on_duplicate_request_index():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verified_cache_states"][7]["request_index"] = 7
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok


def test_parity_fails_when_production_states_missing():
    production, oracle = _load_evidence("C01")
    production = copy.deepcopy(production)
    del production["confirmed_cache_states"]
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok
    assert "confirmed_cache_states" in detail


def test_parity_still_fails_on_verdict_mismatch():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verdict"] = "CONTRACT_MISMATCH"
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok
    assert "verdict" in detail


def test_normalise_rejects_malformed_states():
    assert verify_s0._normalise_cache_states(None, production=False) is None
    assert verify_s0._normalise_cache_states([], production=False) is None
    assert (
        verify_s0._normalise_cache_states(
            [{"request_index": i, "state": "MISS"} for i in range(1, 8)],
            production=False,
        )
        is None
    )
    states = verify_s0._normalise_cache_states(
        [{"request_index": i, "state": "MISS"} for i in range(1, 9)],
        production=False,
    )
    assert states is not None and len(states) == 8
    # Production-side CACHE_STATE_UNKNOWN normalises to None.
    states = verify_s0._normalise_cache_states(
        [
            {"request_index": i, "state": "CACHE_STATE_UNKNOWN"}
            for i in range(1, 9)
        ],
        production=True,
    )
    assert states is not None and all(s["state"] is None for s in states)
    # ... but the Oracle side must not use it.
    assert (
        verify_s0._normalise_cache_states(
            [
                {"request_index": i, "state": "CACHE_STATE_UNKNOWN"}
                for i in range(1, 9)
            ],
            production=False,
        )
        is None
    )
```
