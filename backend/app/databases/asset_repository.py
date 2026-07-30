from hashlib import sha256

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.assets import Asset, DocumentAsset
from app.schemas.assets import AssetWrite


async def replace_document_assets(
    session: AsyncSession,
    *,
    document_version_id: int,
    assets: list[AssetWrite],
) -> None:
    await session.execute(
        delete(DocumentAsset).where(
            DocumentAsset.document_version_id == document_version_id
        )
    )

    seen_asset_keys: set[str] = set()

    for display_order, item in enumerate(assets):
        url = str(item.url)
        asset_key = f"url-{sha256(url.encode('utf-8')).hexdigest()}"

        if asset_key in seen_asset_keys:
            raise ValueError(f"Asset URL bị trùng: {url}")
        seen_asset_keys.add(asset_key)

        asset = await session.scalar(
            select(Asset).where(Asset.asset_key == asset_key)
        )
        if asset is None:
            asset = Asset(
                asset_key=asset_key,
                asset_type=item.asset_type,
                title=item.title,
                url=url,
            )
            session.add(asset)
            await session.flush()
        else:
            asset.title = item.title
            asset.asset_type = item.asset_type

        session.add(
            DocumentAsset(
                document_version_id=document_version_id,
                asset_id=asset.id,
                relation_type="reference",
                display_order=display_order,
            )
        )
