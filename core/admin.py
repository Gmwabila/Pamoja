from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Profile, Task

@admin.register(User)
class PamojaUserAdmin(UserAdmin):
    ordering = ['email']
    list_display = ['email', 'first_name', 'is_staff']
    search_fields = ['email', 'first_name']
    fieldsets = ((None, {'fields': ('email', 'password')}),
                 ('Personal info', {'fields': ('first_name', 'last_name')}),
                 ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
                 ('Dates', {'fields': ('last_login', 'date_joined')}))
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),)
admin.site.register(Profile)
admin.site.register(Task)
