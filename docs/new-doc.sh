#!/bin/bash
# Helper script for creating new documentation entries
# Usage: ./docs/new-doc.sh <type> "title"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TODAY=$(date +%Y-%m-%d)

show_usage() {
    echo "Usage: $0 <type> \"title\""
    echo ""
    echo "Types:"
    echo "  adr      - Architecture Decision Record"
    echo "  journal  - Implementation journal entry"
    echo "  bug      - Bug report"
    echo "  learning - Technical learning/note"
    echo ""
    echo "Examples:"
    echo "  $0 adr \"Use SQLite for token storage\""
    echo "  $0 journal \"Implemented regex tokenizer\""
    echo "  $0 bug \"Proxy fails on malformed JSON\""
    echo "  $0 learning \"GTK4 async patterns\""
}

slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//'
}

get_next_id() {
    local dir="$1"
    local prefix="$2"
    local max=0

    for file in "$dir"/${prefix}*.md; do
        if [[ -f "$file" ]]; then
            num=$(basename "$file" | grep -oE "^[0-9]+" || echo "0")
            if [[ "$num" -gt "$max" ]]; then
                max=$num
            fi
        fi
    done

    printf "%04d" $((max + 1))
}

if [[ $# -lt 2 ]]; then
    show_usage
    exit 1
fi

TYPE="$1"
TITLE="$2"
SLUG=$(slugify "$TITLE")

case "$TYPE" in
    adr)
        DIR="$SCRIPT_DIR/decisions"
        TEMPLATE="$SCRIPT_DIR/templates/ADR_TEMPLATE.md"
        ID=$(get_next_id "$DIR" "")
        FILENAME="${ID}-${SLUG}.md"
        SED_TITLE="s/ADR-XXXX: \[Title\]/ADR-${ID}: ${TITLE}/"
        ;;
    journal)
        DIR="$SCRIPT_DIR/journal"
        TEMPLATE="$SCRIPT_DIR/templates/JOURNAL_TEMPLATE.md"
        FILENAME="${TODAY}-${SLUG}.md"
        SED_TITLE="s/YYYY-MM-DD: \[Brief Title\]/${TODAY}: ${TITLE}/"
        ;;
    bug)
        DIR="$SCRIPT_DIR/bugs"
        TEMPLATE="$SCRIPT_DIR/templates/BUG_TEMPLATE.md"
        ID=$(get_next_id "$DIR" "")
        FILENAME="${ID}-${SLUG}.md"
        SED_TITLE="s/BUG-XXXX: \[Brief Description\]/BUG-${ID}: ${TITLE}/"
        ;;
    learning)
        DIR="$SCRIPT_DIR/learnings"
        TEMPLATE="$SCRIPT_DIR/templates/LEARNING_TEMPLATE.md"
        FILENAME="${SLUG}.md"
        SED_TITLE="s/\[Topic Title\]/${TITLE}/"
        ;;
    *)
        echo "Error: Unknown type '$TYPE'"
        echo ""
        show_usage
        exit 1
        ;;
esac

FILEPATH="$DIR/$FILENAME"

if [[ -f "$FILEPATH" ]]; then
    echo "Error: File already exists: $FILEPATH"
    exit 1
fi

# Copy template and replace title
sed -e "$SED_TITLE" -e "s/YYYY-MM-DD/$TODAY/g" "$TEMPLATE" > "$FILEPATH"

echo "Created: $FILEPATH"
echo ""
echo "Next steps:"
echo "  1. Edit the file to fill in details"
echo "  2. Update the index in $DIR/README.md"
