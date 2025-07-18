import time
from bs4 import BeautifulSoup


from ..shared.exceptions import CrwlError
from ..models.crwl_models import NextData1st, NextData2nd
from ..models.crwl_api_models import CrwlAPIRes
from .crwl_api import CrwlAPI
from ..utils.decorators import retry_on_fail


def get_soup(
    sb,
    url: str,
) -> BeautifulSoup:
    sb.cdp.get(url)
    time.sleep(1)
    page_source = sb.cdp.get_page_source()

    # try:
    #     res.raise_for_status()
    # except Exception:
    #     raise CrwlError(f"Can not get soup!!!. Status code: {res.status_code}")

    return BeautifulSoup(page_source, "html.parser")


def extract_next_data(
    soup: BeautifulSoup,
) -> NextData1st | NextData2nd:
    next_data_tag = soup.select_one("#__NEXT_DATA__")
    if next_data_tag:
        try:
            return NextData1st.model_validate_json(next_data_tag.get_text())
        except Exception:
            pass
        # return NextData2nd.model_validate_json(next_data_tag.get_text())
        try:
            return NextData2nd.model_validate_json(next_data_tag.get_text())
        except Exception:
            pass
    raise CrwlError("Can't extract next data")


def find_game_id(
    next_data: NextData1st | NextData2nd,
) -> int:
    if isinstance(next_data, NextData1st):
        return next_data.props.pageProps.gameInfo.game.game_id
    elif isinstance(next_data, NextData2nd):
        return next_data.props.pageProps.productDetail.game_id


def find_item_type_id(
    next_data: NextData1st | NextData2nd,
) -> int | None:
    if isinstance(next_data, NextData1st):
        if next_data.query.item_name is None:
            return None
        for item_type in next_data.props.pageProps.gameInfo.item_type:
            if item_type.slug == next_data.query.item_name:
                return item_type.id

        return None

    if isinstance(next_data, NextData2nd):
        return next_data.props.pageProps.productDetail.item_type_id

    raise CrwlError("Can't find item type id")


def find_item_info_id(
    next_data: NextData1st | NextData2nd,
) -> int | None:
    if isinstance(next_data, NextData1st):
        if next_data.query.item_info_name is None:
            return None
        for item_type in next_data.props.pageProps.gameInfo.item_type:
            for item_info in item_type.item_info:
                if item_info.slug == next_data.query.item_info_name:
                    return item_info.id

    if isinstance(next_data, NextData2nd):
        return next_data.props.pageProps.productDetail.item_info_id

    raise CrwlError("Can't find item info id")


def find_server_id(
    next_data: NextData1st | NextData2nd,
) -> int | None:
    if isinstance(next_data, NextData1st):
        return next_data.query.server

    elif isinstance(next_data, NextData2nd):
        return next_data.props.pageProps.productDetail.server_id


def find_item_info_group_id(
    next_data: NextData1st | NextData2nd,
) -> int | None:
    if isinstance(next_data, NextData1st):
        return next_data.query.group

    elif isinstance(next_data, NextData2nd):
        return next_data.props.pageProps.productDetail.item_info_group_id


def find_keyword(
    next_data: NextData1st | NextData2nd,
) -> str | None:
    if isinstance(next_data, NextData1st):
        return next_data.query.keyword

    return None


@retry_on_fail(max_retries=3, sleep_interval=2)
def extract_data(
    sb,
    api: CrwlAPI,
    url: str,
) -> CrwlAPIRes:
    soup = get_soup(sb, url)

    next_data = extract_next_data(soup)

    game_id = find_game_id(next_data)
    item_type_id = find_item_type_id(next_data)
    item_info_id = find_item_info_id(next_data)
    server_id = find_server_id(next_data)
    item_info_group_id = find_item_info_group_id(next_data)
    keyword = find_keyword(next_data)

    res = api.product(
        game_id=game_id,
        item_type_id=item_type_id,
        item_info_group_id=item_info_group_id,
        item_info_id=item_info_id,
        server_id=server_id,
        keyword=keyword,
    )

    return res
