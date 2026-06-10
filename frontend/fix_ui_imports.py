import glob
import re

files = glob.glob("/Users/wyl/Desktop/Aurora-Design/frontend/src/components/ui/*.tsx")

for file in files:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        
        # Fix Button, Input imports
        content = re.sub(r"import Button from ['\"]@/components/ui/[Bb]utton['\"]", r"import { Button } from '@/components/ui/button'", content)
        content = re.sub(r"import Input from ['\"]@/components/ui/[Ii]nput['\"]", r"import { Input } from '@/components/ui/input'", content)
        content = re.sub(r"import \{ Check[\w]* \} from \"lucide-react\"", "import { Check } from 'lucide-react'", content) # Lucide icons should be fine but just in case
        
        if content != original_content:
            with open(file, 'w', encoding='utf-8') as f:
                f.write(content)
    except Exception as e:
        print(e)
