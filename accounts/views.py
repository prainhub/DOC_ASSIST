from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User


def login_view(request):

    # If user is already logged in, go straight to chat
    if request.user.is_authenticated:
        return redirect("chat_home")

    error = None

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect("chat_home")
        else:
            error = "Invalid username or password. Please try again."

    return render(request, "accounts/login.html", {"error": error})


def register_view(request):

    # If user is already logged in, go straight to chat
    if request.user.is_authenticated:
        return redirect("chat_home")

    error = None

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            error = "Username and password are required."

        elif User.objects.filter(username=username).exists():
            error = "That username is already taken. Please choose another."

        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            login(request, user)
            return redirect("chat_home")

    return render(request, "accounts/register.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("login")
