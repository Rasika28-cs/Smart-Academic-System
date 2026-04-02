from django.contrib import admin
from .models import Staff, Achievement, Winner, Gallery, NewsItem, UpcomingEvent


# ─────────────────────────────────────────────────────────
# EXISTING REGISTRATIONS — UNCHANGED
# ─────────────────────────────────────────────────────────

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'qualification', 'email', 'order')
    list_editable = ('order',)
    search_fields = ('name', 'email')
    list_filter = ('role',)


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('title', 'date')
    search_fields = ('title',)


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'event_name', 'position', 'date')
    list_filter = ('position',)
    search_fields = ('student_name', 'event_name')


# ─────────────────────────────────────────────────────────
# NEW MODEL REGISTRATIONS
# ─────────────────────────────────────────────────────────

@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    search_fields = ('title',)
    list_filter = ('created_at',)
    ordering = ('-created_at',)


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'date')
    search_fields = ('title', 'description')
    ordering = ('-date',)


@admin.register(UpcomingEvent)
class UpcomingEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'venue', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'date')
    search_fields = ('title', 'description', 'venue')
    ordering = ('date',)