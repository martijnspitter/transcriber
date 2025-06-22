<script lang="ts">
  import { markdownToHtml } from '../lib/markdown';

  export let markdown: string = '';
  let htmlContent: string;

  $: {
    htmlContent = markdownToHtml(markdown);
  }
</script>

<div class="prose prose-sm max-w-none prose-headings:font-semibold prose-headings:text-indigo-700
            prose-h1:text-xl prose-h2:text-lg prose-h3:text-base
            prose-p:text-black prose-p:my-2
            prose-a:text-indigo-600 prose-a:no-underline hover:prose-a:underline
            prose-li:text-black prose-li:my-0.5
            prose-strong:text-black prose-em:text-black
            prose-code:text-black prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded
            prose-pre:bg-gray-100 prose-pre:p-2 prose-pre:my-2 prose-pre:rounded
            prose-pre:code:bg-transparent prose-pre:code:p-0
            prose-hr:my-4 prose-hr:border-gray-300">
  <!-- We're using properly sanitized HTML from our markdownToHtml function -->
  <!-- eslint-disable-next-line svelte/no-at-html-tags -->
  {@html htmlContent}
</div>
