# RecordPrep

<img src="recordprep_icon.svg" alt="RecordPrep icon" width="96" align="right">

A Linux desktop app for preparing court-record PDFs for
[Focus](https://github.com/jessemcg/focus), using the
[Pi coding agent](https://github.com/earendil-works/pi/tree/main/packages/coding-agent)
for AI preparation stages.

- Preserve original page text and images in a citation-aware case bundle.
- Classify pages, organize documents, and map official transcript citations.
- Identify hearing participants and create hearing, report, motion-paper, and minute-order summaries.
- Customize preparation with bundled or personal practice profiles.

## Motions

[Motion-paper preparation](docs/motions-workflow.md)
cover independent titles/dates, boundaries, summaries and Focus publication. Existing
bundles/profiles are not migrated; legacy Resume skips unavailable motion preparation.

## Install

RecordPrep is intentionally distributed as source rather than a Flatpak or Debian
package so that it can be easily modified by a coding agent.
The install has been tested with Ubuntu and Fedora.

With `curl` installed, run as your normal user—not with sudo:

```bash
curl -fsSL https://raw.githubusercontent.com/jessemcg/record-prep/main/scripts/install-bootstrap.sh | bash
```

Installs the latest `main` code into `~/RecordPrep` and asks before installing
missing dependencies. RecordPrep installs fully without Pi or an AI account.
The command becomes available when these installer files are published to `main`.

After confirming RecordPrep is installed, setup offers to install Pi if it is
missing. Press Enter to continue with Pi or type `skip` to finish. For preparation,
open Pi and use `/login` to enter an API key or sign in. Then select an available
model in RecordPrep’s **Model settings**. AI usage may incur provider charges.

Pi authentication does not configure the separate classification endpoint: supply
its vision API URL, model, and API key in **Model settings**. Classification uses
that API; OCR is the only app-owned optional local model.
Embedded PDF text is the default extraction route; local OCR setup is optional
and is not installed by this command.

[Installation options, troubleshooting, and removal](docs/source-install.md)

## Resume or uninstall

### Resume installation

```bash
curl -fsSL https://raw.githubusercontent.com/jessemcg/record-prep/main/scripts/install-bootstrap.sh | bash -s -- --resume
```

### Uninstall RecordPrep

Close RecordPrep, then run:

```bash
"$HOME/.local/bin/recordprep-uninstall"
```

This keeps your source checkout, settings, personal profiles, case documents and Pi.
See [removal options](docs/source-install.md#removal) for optional cleanup.

### Uninstall Pi

Run its official installer and choose **Uninstall Pi**:

```bash
curl -fsSL https://pi.dev/install.sh | sh
```

Pi may also serve other apps; removing it disables their Pi features, including
RecordPrep’s AI preparation. Pi credentials and saved sessions are retained.

## Get started

Launch **RecordPrep** from your applications menu or run `recordprep`. Open
**Model settings** to select the shared Pi model and configure the separate classification endpoint.

Choose a preparation profile, then select PDFs for a new bundle or choose an
existing case bundle. Run the pipeline or use **Resume** to continue prepared
work without resetting it. Open the resulting bundle in Focus.

Customize the included **California Juvenile Dependency** profile or use it as a
starting point for another practice area. See the [user guide](docs/workflow.md).

AI preparation may send record text and page images to configured providers.
Review their confidentiality terms before using sensitive records, and verify
generated work against the original record.

## License

See [LICENSE](LICENSE).
