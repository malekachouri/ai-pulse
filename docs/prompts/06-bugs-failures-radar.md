# Prompt 06: Bugs & Failures Radar

| | |
|---|---|
| **Phase** | 6 of 9 |
| **Send it** | After prompt 05. |
| **What it built in this repository** | Bugs with fix tracking, incident states re-verified on status pages, GitHub advisories, configurable alerts (docs/RADAR.md). |
| **Check before the next prompt** | The Bugs page shows severity only with its basis; incidents are 'active' only when recently verified. |

Paste everything in the box below into Claude Code, in the repository, as one message.

~~~text
Build the Bugs & Failures Radar module for AI Pulse.

Act as a senior DevSecOps and Site Reliability Engineering engineer.
1. Bug intelligence
Collect and display:
- Public GitHub bug reports.
- Critical open issues.
- Newly reported bugs.
- Fixed bugs.
- Regressions.
- Performance issues.
- Compatibility problems.
For each bug display:
- Title.
- Repository.
- Issue number.
- Original URL.
- Status.
- Severity.
- Labels.
- Creation date.
- Last update.
- Affected versions.
- Available fix or pull request.
2. Failure intelligence
Track publicly available:
- Cloud service outages.
- Infrastructure incidents.
- API failures.
- Database incidents.
- AI provider service disruptions.
- Kubernetes and Docker ecosystem incidents.
Display:
- Affected provider.
- Affected service.
- Incident status.
- Start time.
- Resolution time if available.
- Impact.
- Official incident URL.
Differentiate current incidents from historical incidents.
3. Vulnerability intelligence
Integrate:
- NVD.
- CISA KEV.
- Vendor advisories.
Display:
- CVE identifier.
- CVSS score.
- Severity.
- Affected software.
- Exploitation status.
- Published date.
- Patch availability.
- Mitigation.
- Official references.
4. Intelligence dashboard
Create:
- Critical bugs list.
- Newly disclosed vulnerabilities.
- Active incidents.
- Resolved incidents.
- Most affected technologies.
- Vulnerability severity chart.
- Incident history.
- Weekly failure statistics.
5. Alerting
Create alerts for:
- New critical CVEs.
- New actively exploited vulnerabilities.
- Critical software bugs.
- Important service outages.
- Security advisories affecting watched technologies.
Support user-configurable thresholds and preferences.
6. Accuracy and reliability
Never label an issue as critical without a documented severity basis.

Never mark an incident as active based only on an old article.

Use source timestamps and source status information.

Display original references and last verification time.

Implement API integration tests and unit tests.
~~~

Previous: [05](05-ai-engine.md) · Next: [07](07-briefings-notifications.md) · [All prompts](README.md)
