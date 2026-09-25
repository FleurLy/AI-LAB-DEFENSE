# Phishing validation dataset

This local validation set contains 100 harmless synthetic/reconstructed emails:
50 safe and 50 phishing. Labels and categories live only in `manifest.csv`; they
are not inserted into the `.eml` messages.

`source/Phishing_validation_emails.csv` is the immutable source snapshot.
Run `python scripts/improve_validation_dataset.py` from the repository root to
rebuild the controlled authentication-header distribution, diversify the ten
attachments, and recalculate manifest facts from the resulting `.eml` files.

The set is intended for pipeline validation and model prototyping, not as a
standalone production benchmark. No real malware is included.
