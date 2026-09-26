docker ps
 python3 extraction/scripts/replay.py extraction/samples/suspicious/phishing_link.eml
  curl -s -X POST http://localhost:8000/analyze \                                    
      -H "Content-Type: application/json" \
      --data-binary @extraction/data/normalized/mail_000002.json | jq .


      ---

python3 extraction/scripts/replay.py  extraction/datasets/phishing_validation/emails/mail_000039.eml       
curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json"  --data-binary @extraction/data/normalized/mail_000012.json | jq .                                         