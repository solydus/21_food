from django.shortcuts import HttpResponse, get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from recipes.models import (Favorite,
                            Ingredient,
                            Recipe,
                            ShoppingCart,
                            Tag)
from users.models import Subscribe, User

from .shopping_utils import generate_shopping_list
from .filters import SearchFilterIngr, RecipesFilter
from .mixins import CreateDestroyAll
from .paginators import PageNumPagination
from .permissions import IsAuthorOrReadOnly
from .serializers import (FavoriteRecipeSerializer,
                          IngredientSerializer,
                          RecipeSerializer,
                          ShoppingCartSerializer,
                          SubscribeSerializer,
                          TagSerializer)


class RecipeViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    queryset = Recipe.objects.all()
    pagination_class = PageNumPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipesFilter
    serializer_class = RecipeSerializer
    permission_classes = [IsAuthorOrReadOnly]


class TagViewSet(mixins.ListModelMixin,
                 mixins.RetrieveModelMixin,
                 viewsets.GenericViewSet):
    # Запрос, который будет использоваться для получения объектов Tag
    queryset = Tag.objects.all()
    # Сериализатор для преобразования объектов Tag в данные JSON
    serializer_class = TagSerializer


class IngredientViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    """ Добавление в список ингридиентов доступно только через админку """
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (SearchFilterIngr,)
    search_fields = ('^name',)

class IngredientViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.CreateModelMixin,
                        mixins.UpdateModelMixin,
                        mixins.DestroyModelMixin,
                        viewsets.GenericViewSet):
    """ Добавление в список ингридиентов доступно только через админку """
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (SearchFilterIngr,)
    search_fields = ('^name',)

    @action(detail=False, methods=['post'])
    def upload(self, request):
uploaded_file = request.FILES['ingredient_file']
    if uploaded_file.name.endswith('.csv'):
        reader = csv.reader(uploaded_file)
        for row in reader:
            name, measure = row
            Ingredient.objects.create(
                name=name,
                measure=measure
            )
        return Response(status=status.HTTP_200_OK)
    else:
        return Response({
            'error': 'Uploaded file must be a CSV file.'
        }, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionsViewSet(mixins.ListModelMixin,
                           mixins.CreateModelMixin,
                           mixins.RetrieveModelMixin,
                           mixins.UpdateModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet):
    serializer_class = SubscribeSerializer
    permission_classes = [IsAuthenticated, ]
    pagination_class = PageNumPagination

    queryset = Subscribe.objects.none()  # Пустой queryset

    def get_queryset(self):
        return Subscribe.objects.filter(
            user=self.request.user).prefetch_related('author')

class SubscribeCreateView(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated] 
    serializer_class = SubscribeSerializer

    def create(self, request, author_id):
        author = get_object_or_404(User, id=author_id)
        if request.user == author:
            return Response(
                {'errors': 'Вы не можете подписаться на самого себя'},
                status=status.HTTP_400_BAD_REQUEST)
        subscription = Subscribe.objects.filter(
            author=author, user=request.user)
        if subscription.exists():
            return Response(
                {'errors': 'Вы уже подписаны на этого автора'},
                status=status.HTTP_400_BAD_REQUEST)
        queryset = Subscribe.objects.create(author=author, user=request.user)
        serializer = self.get_serializer(queryset)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, author_id):
        author = get_object_or_404(User, id=author_id)
        subscription = Subscribe.objects.filter(author=author,
                                                user=request.user)
        if not subscription.exists():
            return Response(
                {'errors': 'Вы еще не подписаны на этого автора'},
                status=status.HTTP_400_BAD_REQUEST)
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubscribeCreateView(APIView):
    """ сделать/удалить подписку """
    permission_classes = [IsAuthenticated, ]

    def post(self, request, author_id):
        author = get_object_or_404(User, id=author_id)
        if request.user == author:
            return Response(
                {'errors': 'Вы не можете подписаться на самого себя'},
                status=status.HTTP_400_BAD_REQUEST)
        subscription = Subscribe.objects.filter(
            author=author, user=request.user)
        if subscription.exists():
            return Response(
                {'errors': 'Вы уже подписаны на этого автора'},
                status=status.HTTP_400_BAD_REQUEST)
        queryset = Subscribe.objects.create(author=author, user=request.user)
        serializer = SubscribeSerializer(
            queryset, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, author_id):
        user = request.user
        author = get_object_or_404(User, id=author_id)
        subscription = Subscribe.objects.filter(
            author=author, user=user)
        if not subscription.exists():
            return Response(
                {'errors': 'Вы еще не подписаны на этого автора'},
                status=status.HTTP_400_BAD_REQUEST)
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    serializer_class = FavoriteRecipeSerializer
    permission_classes = [IsAuthenticated, ]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({'recipe': self.kwargs.get('recipe_id')})
        return context

    def perform_create(self, serializer):
        recipe = get_object_or_404(Recipe, pk=self.kwargs.get('recipe_id'))
        serializer.save(
            recipe_lover=self.request.user, recipe=recipe)

    @action(methods=('delete',), detail=True)
    def delete(self, request, recipe_id):
        recipe = self.kwargs.get('recipe_id')
        recipe_lover = self.request.user
        if not Favorite.objects.filter(recipe=recipe,
                                       recipe_lover=recipe_lover).exists():
            return Response({'errors': 'Рецепт не в избранном'},
                            status=status.HTTP_400_BAD_REQUEST)
        get_object_or_404(
            Favorite,
            recipe_lover=recipe_lover,
            recipe=recipe).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShoppingCartViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ShoppingCartSerializer

    def get_queryset(self):
        return ShoppingCart.objects.filter(cart_owner=self.request.user)

    def perform_create(self, serializer):
        recipe = get_object_or_404(Recipe,
                                   pk=self.kwargs.get('recipe_id'))
        serializer.save(recipe=recipe,
                        cart_owner=self.request.user)

    @action(methods=['delete'], detail=True)
    def delete(self, request, recipe_id):
        recipe = get_object_or_404(Recipe,
                                   pk=recipe_id)
        if not ShoppingCart.objects.filter(
            recipe=recipe,
            cart_owner=self.request.user).exists():
           return Response({"errors"...})
        ShoppingCart.objects.filter(
            recipe=recipe,
            cart_owner=self.request.user
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DownloadShoppingCart(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shopping_list = generate_shopping_list(request.user)
        if not shopping_list:
            return Response({"errors": ...})
        response = HttpResponse(
                  shopping_list,
                  content_type='text/plain')
        response['Content-Disposition'] = \
            'attachment; filename="shopping_list.txt"'
        return response
