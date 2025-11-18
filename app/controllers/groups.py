"""Endpoints for group creation and membership management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.controllers.dependencies import CurrentUserDep, SessionDep
from app.models.group import Group
from app.models.group_membership import (
    GroupMembership,
    GroupMembershipStatus,
    GroupRole,
)
from app.models.user import AccountType, User as UserModel
from app.views import (
    GroupCreateRequest,
    GroupMemberResponse,
    GroupMembershipCreateRequest,
    GroupMembershipResponse,
    GroupResponse,
    GroupUpdateRequest,
)

router = APIRouter(prefix="/groups", tags=["groups"])


async def _get_group_or_404(session: SessionDep, group_id: int) -> Group:
    result = await session.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    return group


async def _get_membership(
    session: SessionDep,
    group_id: int,
    user_id: int,
) -> GroupMembership | None:
    result = await session.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


def _serialize_group(group: Group, membership: GroupMembership | None) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        schoolId=group.school_id,
        ownerId=group.owner_id,
        membershipRole=membership.role if membership else None,
        membershipStatus=membership.status if membership else None,
        createdAt=group.created_at,
        updatedAt=group.updated_at,
    )


def _serialize_membership(
    membership: GroupMembership,
    user: UserModel | None = None,
) -> GroupMemberResponse:
    return GroupMemberResponse(
        id=membership.id,
        groupId=membership.group_id,
        userId=membership.user_id,
        role=membership.role,
        status=membership.status,
        invitedById=membership.invited_by_id,
        createdAt=membership.created_at,
        updatedAt=membership.updated_at,
        email=user.email if user else None,
        firstName=user.first_name if user else None,
        lastName=user.last_name if user else None,
    )


def _ensure_instructor(current_user: CurrentUserDep) -> None:
    if current_user.account_type != AccountType.INSTRUCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instructors can perform this action",
        )
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assign an academy to your profile first",
        )


@router.get("/", response_model=list[GroupResponse])
async def list_groups(
    current_user: CurrentUserDep,
    session: SessionDep,
) -> list[GroupResponse]:
    """Return groups that belong to the instructor or where the student is a member."""

    if current_user.account_type == AccountType.INSTRUCTOR:
        result = await session.execute(
            select(Group)
            .where(Group.owner_id == current_user.id)
            .order_by(Group.name)
        )
        groups = result.scalars().all()
        if not groups:
            return []
        membership_rows = await session.execute(
            select(GroupMembership).where(
                GroupMembership.group_id.in_([group.id for group in groups]),
                GroupMembership.user_id == current_user.id,
            )
        )
        membership_map = {
            membership.group_id: membership
            for membership in membership_rows.scalars().all()
        }
        return [
            _serialize_group(group, membership_map.get(group.id))
            for group in groups
        ]

    result = await session.execute(
        select(Group, GroupMembership)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(GroupMembership.user_id == current_user.id)
        .order_by(Group.name)
    )
    rows = result.all()
    return [
        _serialize_group(group, membership)
        for group, membership in rows
    ]


@router.post(
    "/",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group(
    payload: GroupCreateRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> GroupResponse:
    """Allow an instructor to create a group within their academy."""

    _ensure_instructor(current_user)

    name = payload.name.strip()
    description = payload.description.strip() if payload.description else None
    duplicate = await session.execute(
        select(func.count(Group.id)).where(
            func.lower(Group.name) == name.lower(),
            Group.school_id == current_user.school_id,
        )
    )
    if duplicate.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another group with this name already exists in your academy",
        )

    group = Group(
        name=name,
        description=description,
        school_id=current_user.school_id,
        owner_id=current_user.id,
    )
    session.add(group)
    owner_membership = GroupMembership(
        group=group,
        user_id=current_user.id,
        role=GroupRole.INSTRUCTOR,
        status=GroupMembershipStatus.ACTIVE,
        invited_by_id=current_user.id,
    )
    session.add(owner_membership)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create group",
        ) from exc

    await session.refresh(group)
    await session.refresh(owner_membership)
    return _serialize_group(group, owner_membership)


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> GroupResponse:
    """Return a single group if it belongs to the current user."""

    group = await _get_group_or_404(session, group_id)
    membership = await _get_membership(session, group_id, current_user.id)
    if membership is None and group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not belong to this group",
        )

    if membership is None and group.owner_id == current_user.id:
        membership = GroupMembership(
            group_id=group.id,
            user_id=current_user.id,
            role=GroupRole.INSTRUCTOR,
            status=GroupMembershipStatus.ACTIVE,
            invited_by_id=current_user.id,
        )

    return _serialize_group(group, membership)


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    payload: GroupUpdateRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> GroupResponse:
    """Update group metadata (name/description)."""

    group = await _get_group_or_404(session, group_id)
    if group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can update it",
        )

    updated = False
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name cannot be empty",
            )
        duplicate = await session.execute(
            select(Group).where(
                Group.id != group.id,
                Group.school_id == group.school_id,
                func.lower(Group.name) == new_name.lower(),
            )
        )
        if duplicate.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another group in this academy already uses that name",
            )
        group.name = new_name
        updated = True
    if payload.description is not None:
        group.description = payload.description.strip() or None
        updated = True

    if updated:
        await session.commit()
        await session.refresh(group)

    membership = await _get_membership(session, group_id, current_user.id)
    if membership is None:
        membership = GroupMembership(
            group_id=group.id,
            user_id=current_user.id,
            role=GroupRole.INSTRUCTOR,
            status=GroupMembershipStatus.ACTIVE,
            invited_by_id=current_user.id,
        )

    return _serialize_group(group, membership)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Response:
    """Delete a group owned by the instructor."""

    group = await _get_group_or_404(session, group_id)
    if group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can delete it",
        )

    await session.delete(group)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_group_members(
    group_id: int,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> list[GroupMemberResponse]:
    """Return members and pending invitations for a group."""

    group = await _get_group_or_404(session, group_id)
    membership = await _get_membership(session, group_id, current_user.id)
    if membership is None and group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not belong to this group",
        )

    result = await session.execute(
        select(GroupMembership, UserModel)
        .join(UserModel, UserModel.id == GroupMembership.user_id)
        .where(GroupMembership.group_id == group_id)
        .order_by(UserModel.first_name, UserModel.last_name)
    )
    rows = result.all()
    return [
        _serialize_membership(membership_row, user)
        for membership_row, user in rows
    ]


@router.post(
    "/{group_id}/members",
    response_model=GroupMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_group_member(
    group_id: int,
    payload: GroupMembershipCreateRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> GroupMembershipResponse:
    """Allow an instructor to add a student immediately."""

    group = await _get_group_or_404(session, group_id)
    if group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can add students",
        )

    result = await session.execute(
        select(UserModel).where(UserModel.id == payload.userId)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    if student.account_type != AccountType.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only students can join a group",
        )
    if student.school_id != group.school_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student must belong to the same academy as the group",
        )

    membership = await _get_membership(session, group_id, student.id)
    if membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student already belongs to this group",
        )

    membership = GroupMembership(
        group_id=group.id,
        user_id=student.id,
        role=GroupRole.STUDENT,
        status=GroupMembershipStatus.ACTIVE,
        invited_by_id=current_user.id,
    )
    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return GroupMembershipResponse.model_validate(membership)


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_group_member(
    group_id: int,
    user_id: int,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> Response:
    """Remove a student or allow members to leave."""

    group = await _get_group_or_404(session, group_id)
    membership = await _get_membership(session, group_id, user_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    if user_id == current_user.id:
        if group.owner_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The owner cannot leave their own group",
            )
        await session.delete(membership)
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can remove other members",
        )
    if membership.user_id == group.owner_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The owner cannot be removed",
        )

    await session.delete(membership)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
