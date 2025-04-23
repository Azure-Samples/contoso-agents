import re
import logging
from botbuilder.schema import InputHints, Activity
from botbuilder.core import MessageFactory, CardFactory
from semantic_kernel.contents import ChatMessageContent

logger = logging.getLogger(__name__)


def create_adaptive_card_from_content(chat_message: ChatMessageContent) -> Activity:
    """
    Creates an Adaptive Card that can render both text and tables in the content.

    Args:
        chat_message (ChatMessageContent): The chat message content to render

    Returns:
        Activity: A bot activity containing the adaptive card
    """
    content = chat_message.content

    # Check if the content contains a markdown table
    table_pattern = r"\|(.+)\|\n\|(\s*[-:]+[-:|\s]*)\|\n(\|.+\|\n)+"
    has_table = bool(re.search(table_pattern, content))

    if not has_table:
        # No table, use simple text block
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.3",
            "body": [
                {
                    "type": "TextBlock",
                    "text": content,
                    "wrap": True
                }
            ]
        }
    else:
        # Extract tables and text into separate sections
        body_elements = []

        # Split content at tables
        parts = re.split(table_pattern, content)

        # Process each part
        remaining_content = content

        # Find all tables
        tables = re.findall(table_pattern, content)

        # If there are tables, process text and tables alternatively
        if tables:
            table_matches = list(re.finditer(table_pattern, content))
            last_end = 0

            for match in table_matches:
                # Add text before table
                pre_text = remaining_content[last_end:match.start()].strip()
                if pre_text:
                    body_elements.append({
                        "type": "TextBlock",
                        "text": pre_text,
                        "wrap": True
                    })

                # Process and add table
                table_text = match.group(0)
                table_data = parse_markdown_table(table_text)

                if table_data:
                    body_elements.append(create_table_element(table_data))

                last_end = match.end()

            # Add text after last table
            post_text = remaining_content[last_end:].strip()
            if post_text:
                body_elements.append({
                    "type": "TextBlock",
                    "text": post_text,
                    "wrap": True
                })
        else:
            # Fallback if table parsing fails
            body_elements.append({
                "type": "TextBlock",
                "text": content,
                "wrap": True
            })

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.3",
            "body": body_elements
        }

    logger.info(f"Generated adaptive card for content with{'out' if not has_table else ''} table")
    return MessageFactory.attachment(
        CardFactory.adaptive_card(card),
        input_hint=InputHints.accepting_input
    )


def parse_markdown_table(table_text: str) -> dict:
    """
    Parses a markdown table into header and rows.

    Args:
        table_text (str): The markdown table text

    Returns:
        dict: Dictionary with headers and rows
    """
    lines = table_text.strip().split('\n')
    if len(lines) < 3:  # Need at least header, separator, and one data row
        return None

    # Extract headers
    headers = [cell.strip() for cell in lines[0].strip('|').split('|')]

    # Extract rows
    rows = []
    for line in lines[2:]:  # Skip header and separator lines
        if '|' not in line:
            continue
        row_cells = [cell.strip() for cell in line.strip('|').split('|')]
        rows.append(row_cells)

    return {
        "headers": headers,
        "rows": rows
    }


def create_table_element(table_data: dict) -> dict:
    """
    Creates an Adaptive Card ColumnSet to represent a table.

    Args:
        table_data (dict): Dictionary with headers and rows

    Returns:
        dict: Adaptive card element representing a table
    """
    if not table_data or not table_data.get("headers") or not table_data.get("rows"):
        return {"type": "TextBlock", "text": "Could not render table", "wrap": True}

    table_elements = []

    # Add header row
    header_columns = []
    for header in table_data["headers"]:
        header_columns.append({
            "type": "Column",
            "width": "stretch",
            "items": [
                {
                    "type": "TextBlock",
                    "text": header,
                    "weight": "Bolder",
                    "wrap": True
                }
            ]
        })

    table_elements.append({
        "type": "ColumnSet",
        "columns": header_columns
    })

    # Add separator
    table_elements.append({
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": " ",
                        "separator": True
                    }
                ]
            }
        ]
    })

    # Add data rows
    for row in table_data["rows"]:
        row_columns = []
        for i, cell in enumerate(row):
            if i >= len(table_data["headers"]):
                break  # Skip cells without corresponding header

            row_columns.append({
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": cell,
                        "wrap": True
                    }
                ]
            })

        # Ensure we have a column for each header
        while len(row_columns) < len(table_data["headers"]):
            row_columns.append({
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "",
                        "wrap": True
                    }
                ]
            })

        table_elements.append({
            "type": "ColumnSet",
            "columns": row_columns
        })

    # Container to hold the entire table with a light background
    return {
        "type": "Container",
        "style": "emphasis",
        "items": table_elements,
        "bleed": True
    }
