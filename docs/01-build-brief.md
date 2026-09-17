# 01, Build Brief

## The product in one paragraph

A web tool, accessed by invited Adaptavate partners only, in which a prospective
licensee enters their own plant parameters and sees the technical, carbon and
commercial case for converting their plasterboard production line to GypBlack.
The tool exists to move a partner conversation from an abstract pitch to a
concrete, numbers-based discussion about their specific facility. It is a sales
and partner-acquisition instrument, not an engineering design tool.

## Who uses it

**Primary: a prospective partner.** A commercial or technical decision maker at
a plasterboard manufacturer, evaluating whether converting a line is worth
pursuing. They are not an Adaptavate employee and must never see the underlying
model. They see a simplified control panel and a results dashboard.

**Secondary: Adaptavate internal.** The brief describes a fuller "Adaptavate
Mode" with access to raw parameters for internal scenario modelling. The brief
explicitly ranks this as a lower priority for Phase 1, "nice to have if time
allows". The prototype demonstrates the concept lightly. Do not build this out
at the expense of the partner-facing path.

## In scope for Phase 1

- The eight-input control panel, exactly as specified in `docs/04-io-contract.md`
- The six output modules, exactly as specified in `docs/04-io-contract.md`
- Server-side calculation using Adaptavate's real model
- Admin-issued login access, no public sign-up
- Staging and live hosted environments with automated deployment
- A results view that works on a laptop and on a phone, partners will open this
  on a phone at a conference

## Explicitly out of scope for Phase 1

The original client brief names these as excluded. Do not build them, do not
scaffold for them, do not let them expand the estimate.

- Live IoT or sensor feeds from a plant
- Machine learning or optimisation suggestions
- Public self-service sign-up or account creation
- Payment or billing
- A partner-facing report export (this is Tier 3, a separate later stage)

## Deliberately deferred to later tiers

Mentioned only so you can build without painting us into a corner. Do not build
these now, but do not make them impossible either.

- **Tier 2 remainder:** a database storing scenario inputs and outputs per
  partner, so we can see what partners modelled. Structure is still being agreed
  with Adaptavate. Build the calculation service so that adding a persistence
  layer later does not mean restructuring it.
- **Tier 3:** an automated quarterly partner report comparing a live partner's
  actual production against the scenario they modelled here. This is why
  persisting the input scenario matters later.

## Definition of success on 7 October

An invited partner can open a link on their own device at the conference, enter
their plant's real numbers, and see credible results calculated by Adaptavate's
actual model, with no possibility of extracting the formulas behind it.
