import os
import praw
from dotenv import load_dotenv
from google.adk.agents import Agent
from praw.exceptions import PRAWException
from typing import TypedDict, List, Optional
from dataclasses import dataclass

@dataclass
class PostAnalysis:
    title: str
    content: str
    url: str
    author: str
    score: int
    positive_comments: List[str]
    negative_comments: List[str]
    total_comments: int

class PostData(TypedDict):
    title: str
    content: str
    post_id: str

def get_reddit_news(subreddit: str, limit: int = 10) -> dict[str, List[PostData]]:
    """
    Fetches top posts from a specified subreddit using the Reddit API.

    Args:
        subreddit: The name of the subreddit to fetch news from (e.g., 'SideProject').
        limit: The maximum number of top posts to fetch.

    Returns:
        A dictionary with the subreddit name as key and a list of
        post data (title, content, and post_id) as value.
    """
    print(f"--- Tool called: Fetching from r/{subreddit} via Reddit API ---")
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")

    if not all([client_id, client_secret, user_agent]):
        print("--- Tool error: Reddit API credentials missing in .env file. ---")
        return {subreddit: [{"title": "Error", "content": "Reddit API credentials not configured.", "post_id": ""}]}

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        reddit.subreddits.search_by_name(subreddit, exact=True)
        sub = reddit.subreddit(subreddit)
        top_posts = list(sub.hot(limit=limit))
        
        posts_data = []
        for post in top_posts:
            content = post.selftext if post.selftext else post.url
            posts_data.append({
                "title": post.title,
                "content": content,
                "post_id": post.id
            })
            
        if not posts_data:
            return {subreddit: [{"title": "No posts", "content": f"No recent hot posts found in r/{subreddit}.", "post_id": ""}]}
        return {subreddit: posts_data}
    except PRAWException as e:
        print(f"--- Tool error: Reddit API error for r/{subreddit}: {e} ---")
        return {subreddit: [{"title": "Error", "content": f"Error accessing r/{subreddit}. It might be private, banned, or non-existent. Details: {e}", "post_id": ""}]}
    except Exception as e:
        print(f"--- Tool error: Unexpected error for r/{subreddit}: {e} ---")
        return {subreddit: [{"title": "Error", "content": f"An unexpected error occurred while fetching from r/{subreddit}.", "post_id": ""}]}

def analyze_post_and_comments(subreddit: str, post_id: str, comment_limit: int = 20) -> dict[str, PostAnalysis]:
    """
    Analyzes a specific post and its comments, providing comprehensive details about both.

    Args:
        subreddit: The name of the subreddit where the post is located.
        post_id: The ID of the post to analyze.
        comment_limit: Maximum number of top-level comments to analyze.

    Returns:
        A dictionary containing the complete analysis of the post and its comments.
    """
    print(f"--- Tool called: Analyzing post and comments for {post_id} in r/{subreddit} ---")
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")

    if not all([client_id, client_secret, user_agent]):
        print("--- Tool error: Reddit API credentials missing in .env file. ---")
        return {"error": PostAnalysis("Error", "Reddit API credentials not configured.", "", "", 0, [], [], 0)}

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        
        # Get the post
        post = reddit.submission(id=post_id)
        
        # Get post details
        post_title = post.title
        post_content = post.selftext if post.selftext else "No text content (link post)"
        post_url = post.url
        post_author = str(post.author)
        post_score = post.score
        
        # Fetch and analyze comments
        positive_comments = []
        negative_comments = []
        total_comments = 0
        
        # Replace MoreComments objects with actual comments
        post.comments.replace_more(limit=0)
        
        for comment in post.comments.list()[:comment_limit]:
            total_comments += 1
            # Simple sentiment analysis based on upvotes and content
            if comment.score > 0:
                positive_comments.append(comment.body)
            elif comment.score < 0:
                negative_comments.append(comment.body)
        
        return {
            post_id: PostAnalysis(
                title=post_title,
                content=post_content,
                url=post_url,
                author=post_author,
                score=post_score,
                positive_comments=positive_comments,
                negative_comments=negative_comments,
                total_comments=total_comments
            )
        }
        
    except Exception as e:
        print(f"--- Tool error: Failed to analyze post {post_id}: {e} ---")
        return {"error": PostAnalysis("Error", str(e), "", "", 0, [], [], 0)}

# Define the Agent
agent = Agent(
    name="reddit_scout_agent",
    description="A Reddit scout agent that searches for and summarizes posts from a given subreddit",
    model="gemini-2.0-flash",
    instruction=(
        "You are the Reddit News Scout. Your primary task is to fetch and summarize news from a given subreddit."
        "1. **Identify Intent:** Determine if the user is asking for:\n"
        "   - A list of posts from a subreddit (initial request)\n"
        "   - Details about a specific post (follow-up request)\n"
        "2. **Determine Subreddit:** Identify which subreddit(s) to check. Use 'sideproject' by default if none are specified."
        "3. **Initial Post Fetching:** When asked for posts or summaries:\n"
        "   - Call `get_reddit_news` with the identified subreddit\n"
        "   - Store the returned post IDs for future reference\n"
        "   - For each post, format the response as:\n"
        "     * The post title\n"
        "     * A brief 1-2 sentence summary\n"
        "   - Present in a clear, bulleted format"
        "4. **Detailed Post Analysis:** When asked about a specific post:\n"
        "   - Match the post title from the user's question with your stored posts\n"
        "   - Use the exact post ID from your stored data\n"
        "   - Call `analyze_post_and_comments` with the subreddit and post_id\n"
        "   - Provide a comprehensive analysis:\n"
        "     * Full post title and author\n"
        "     * Detailed summary of the post content\n"
        "     * Post score and URL\n"
        "     * Key points from positive comments\n"
        "     * Key points from negative comments\n"
        "     * Total comments analyzed\n"
        "   - Format the response to clearly separate post content from community feedback"
        "5. **Context Maintenance:**\n"
        "   - ALWAYS keep track of the post IDs from your last `get_reddit_news` call\n"
        "   - When a user asks about a specific post, use the stored ID\n"
        "   - If you can't find the post ID, ask the user to first list the posts"
        "6. **Error Handling:**\n"
        "   - If post not found in context: Ask user to first get the post list\n"
        "   - If API errors occur: Report the error message clearly"
    ),
    tools=[get_reddit_news, analyze_post_and_comments],
)