# Clean-room policy (DRAFT v0.1)

Status: draft for review. This is not legal advice. Have a qualified lawyer review it before
the project accepts outside contributions or publishes releases.

## Why this exists

Compatibility work is legitimate when it is built from observed behavior and public
documentation. It becomes a liability when code is derived from proprietary source or from
decompiled output. Wine and ReactOS both refuse contributions from people who have seen
leaked or decompiled Windows code; this project follows the same rule so its work can be
upstreamed.

## Roles

- **Analysts** study software (black-box behavior, public interfaces, protocol traces,
  documented file formats) and write **specifications**. Analysts may use reverse-engineering
  tools, including AI agents such as REA, inside the quarantine environment.
- **Implementers** write code from specifications and public documentation only. An implementer,
  human or AI session, must never have seen decompiled output, disassembly, or leaked source
  for the component they implement.
- **Verifiers** run behavior tests comparing the implementation with the real software on
  hardware and licenses the project legally holds.

One person or agent session must not hold the analyst and implementer role for the same component.

## Rules

1. Raw decompiled or disassembled output stays inside the quarantine environment. Only written
   specifications leave it. Specifications describe behavior (inputs, outputs, edge cases,
   message formats), not code structure, names of private functions, or copied constants
   beyond what interoperability requires.
2. Implementers receive specifications and public documentation only.
3. Every pull request touching compatibility code includes a provenance statement: which spec
   it implements and a declaration that the author has not seen proprietary source or decompiled
   output for that component.
4. AI-assisted implementation sessions start from the spec, with no analysis transcripts or
   decompiler output in context.
5. No AI-written kernel or driver code. Changes to system components go through sandboxed CI
   and staged rollout.
6. Do not use Microsoft, Apple, or Adobe names or logos in product branding. Describe
   compatibility factually ("opens DOCX files").
7. Do not circumvent technical protection measures or impersonate vendor devices to vendor
   services. Features that need that stay out of the core product.

## Open items for legal review

- Patent exposure for clone applications (vendors hold patents on specific features).
- Whether use of reference renders from commercial apps for parity testing is permitted under
  their license terms.
- Jurisdiction-specific rules on interoperability exceptions to reverse-engineering limits.
- Choice of project license and contributor agreement.
