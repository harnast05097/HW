#!/usr/bin/env bash

BASE_URL="http://hw1.alexbers.com/"
TOKEN="41730816355b3bf87bd7425dac14fdd5"

WORK_DIR=$(mktemp -d)
RESPONSE_FILE="$WORK_DIR/response.html"
trap 'rm -r "$WORK_DIR"' EXIT

extract_target_path() {
    local response_file="$1"
    local response_text
    local address_pattern='по адресу.*<code> *(/[a-zA-Z0-9_-]+) *</code>'
    local link_pattern="href=['\"]([^'\"]+)['\"]"

    response_text=$(<"$response_file")
    if [[ $response_text =~ $address_pattern ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    elif [[ $response_text =~ $link_pattern ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    fi
}

step=1

echo "[GET] $BASE_URL"
curl -sS -L -H "Cookie: user=$TOKEN" \
    -o "$RESPONSE_FILE" "$BASE_URL" || exit 1

while true; do
    response_text=$(<"$RESPONSE_FILE")
    if [[ "${response_text,,}" == *поздравляем* ]]; then
        echo "Секрет получен"
        cat "$RESPONSE_FILE"
        break
    fi

    echo "ШАГ #$step"

    target_path=$(extract_target_path "$RESPONSE_FILE")

    if [ -z "$target_path" ]; then
        echo "URL не найден"
        break
    fi

    if [[ "$target_path" =~ ^https?:// ]]; then
        target_url="$target_path"
    elif [[ "$target_path" == /* ]]; then
        target_url="${BASE_URL%/}$target_path"
    else
        target_url="${BASE_URL%/}/$target_path"
    fi

    cookie_header="user=$TOKEN"
    header_args=()
    query_args=()
    form_args=()
    file_names=()
    file_contents=()

    while IFS=$'\t' read -r kind key value; do
        case "$kind" in
            cookie) cookie_header+="; $key=$value" ;;
            header) header_args+=(-H "$key: $value") ;;
            query) query_args+=(--url-query "$key=$value") ;;
            form) form_args+=(--data-urlencode "$key=$value") ;;
            file)
                file_names+=("$key")
                file_contents+=("$value")
                ;;
        esac
    done < <(awk '
    function clean(text) {
        gsub(/<[^>]*>/, "", text)
        gsub(/[\t\r\n]/, " ", text)
        sub(/^ +/, "", text)
        sub(/ +$/, "", text)
        return text
    }
    BEGIN { RS = "</table>" }
    {
        if (!/<table/) next

        context = $0
        sub(/<table.*/, "", context)
        gsub(/<[^>]*>/, " ", context)
        context = tolower(context)

        kind = ""
        if (index(context, "cookie")) kind = "cookie"
        else if (index(context, "заголовки")) kind = "header"
        else if (index(context, "параметры запроса")) kind = "query"
        else if (index(context, "данные формы")) kind = "form"
        else if (index(context, "указанным содержимым")) kind = "file"
        if (kind == "") next

        table = $0
        sub(/^.*<table[^>]*>/, "", table)
        row_count = split(table, rows, /<tr[^>]*>/)
        for (row = 2; row <= row_count; row++) {
            cell_count = split(rows[row], cells, /<td[^>]*>/)
            if (cell_count < 3) continue

            key = clean(cells[2])
            value = clean(cells[3])
            if (key != "") print kind "\t" key "\t" value
        }
    }
    ' "$RESPONSE_FILE")

    curl_args=(-sS -L -H "Cookie: $cookie_header")
    curl_args+=("${header_args[@]}" "${query_args[@]}")

    if [[ $response_text == *POST* ]] || [ "${#file_names[@]}" -gt 0 ]; then
        if [ "${#file_names[@]}" -gt 0 ]; then
            echo "[POST Files] $target_url"
            for file_index in "${!file_names[@]}"; do
                file_name="${file_names[$file_index]}"
                file_path="$WORK_DIR/upload_$file_index"
                printf '%s' "${file_contents[$file_index]}" > "$file_path"
                curl_args+=(-F "$file_name=@$file_path;filename=$file_name")
            done
        else
            echo "[POST Data] $target_url"
            curl_args+=("${form_args[@]}")
            if [ "${#form_args[@]}" -eq 0 ]; then
                curl_args+=(--data '')
            fi
        fi
    else
        echo "[GET] $target_url"
    fi

    curl "${curl_args[@]}" -o "$RESPONSE_FILE" "$target_url" || exit 1

    step=$((step + 1))
done