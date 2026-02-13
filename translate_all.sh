#!/bin/bash
# Script to translate TTM_EN.json to all supported languages
# Uses dual-reference mode (EN + RU) for best quality

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🌍 Starting batch translation for all languages...${NC}\n"

# Array of locale codes and their full names (from languages.yml)
declare -a LOCALES=(
    "bg:Bulgarian"
    "zh-Hans:Chinese (Simplified)"
    "nl:Dutch"
    "fr:French"
    "de:German"
    "hi:Hindi"
    "id:Indonesian"
    "ja:Japanese"
    "ko:Korean"
    "ms:Malay"
    "pl:Polish"
    "pt:Portuguese"
    "pt-br:Portuguese (Brazil)"
    "es:Spanish"
    "tl:Tagalog"
    "th:Thai"
    "tr:Turkish"
    "uk:Ukrainian"
    "vi:Vietnamese"
)

# Track statistics
TOTAL=${#LOCALES[@]}
SUCCESS=0
FAILED=0
SKIPPED=0

# Create data directory if it doesn't exist
mkdir -p data

# Function to convert locale to uppercase filename format
locale_to_filename() {
    local locale="$1"
    # Replace hyphens with underscores and convert to uppercase
    echo "$locale" | tr '[:lower:]' '[:upper:]' | tr '-' '_'
}

# Process each language
for locale_info in "${LOCALES[@]}"; do
    IFS=':' read -r locale name <<< "$locale_info"
    
    # Generate proper filename (e.g., zh-Hans -> ZH_HANS)
    FILENAME_SUFFIX=$(locale_to_filename "$locale")
    OUTPUT_FILE="data/TTM_${FILENAME_SUFFIX}.json"
    
    # Skip if already exists
    if [ -f "$OUTPUT_FILE" ]; then
        echo -e "${YELLOW}⏭️  Skipping $name ($locale) - already exists: $OUTPUT_FILE${NC}"
        ((SKIPPED++))
        continue
    fi
    
    echo -e "\n${GREEN}🚀 Translating to $name ($locale)...${NC}"
    echo -e "${BLUE}   Output: $OUTPUT_FILE${NC}"
    
    # Run translation with dual-reference mode
    if make translate \
        LOCALE="$locale" \
        SOURCE_EN=data/TTM_EN.json \
        SOURCE_RU=data/TTM_RU.json \
        OUT_DST="$OUTPUT_FILE"; then
        
        echo -e "${GREEN}✅ $name completed!${NC}"
        ((SUCCESS++))
    else
        echo -e "${RED}❌ $name failed!${NC}"
        ((FAILED++))
    fi
    
    # Small delay between languages to avoid rate limits
    sleep 2
done

# Print summary
echo -e "\n${BLUE}================================================${NC}"
echo -e "${BLUE}📊 Translation Summary:${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "Total languages: $TOTAL"
echo -e "${GREEN}✅ Successful: $SUCCESS${NC}"
echo -e "${YELLOW}⏭️  Skipped (already exist): $SKIPPED${NC}"
echo -e "${RED}❌ Failed: $FAILED${NC}"
echo -e "${BLUE}================================================${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All translations completed successfully!${NC}"
    echo -e "\n${BLUE}📦 Generated files in data/:${NC}"
    ls -lh data/TTM_*.json | tail -n +2 | awk '{print "  - " $9 " (" $5 ")"}'
    exit 0
else
    echo -e "\n${RED}⚠️  Some translations failed. Check logs above.${NC}"
    exit 1
fi
